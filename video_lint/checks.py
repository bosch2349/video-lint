import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import ffmpeg_filters as ff


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


_SEVERITY = {Status.PASS: 0, Status.SKIP: 0, Status.WARN: 1, Status.FAIL: 2}


def worst_status(*statuses: Status) -> Status:
    return max(statuses, key=lambda s: _SEVERITY[s])


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    details: dict = field(default_factory=dict)


DEFAULT_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.json"


def load_thresholds(config_path: Path = None) -> dict:
    with open(config_path or DEFAULT_THRESHOLDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _ffmpeg_skip_result(name: str, error: Exception) -> CheckResult:
    if isinstance(error, FileNotFoundError):
        return CheckResult(name, Status.SKIP, "ffmpeg not found (check that ffmpeg is installed)")
    return CheckResult(name, Status.SKIP, f"Skipped check due to ffmpeg execution failure: {error}")


_ALLOWED_CODECS = {"h264", "hevc"}
_ALLOWED_RATIOS = {
    "9:16": 9 / 16,
    "1:1": 1.0,
    "16:9": 16 / 9,
}
_RATIO_TOLERANCE = 0.02


def check_codec_resolution(probe: dict) -> CheckResult:
    name = "codec/resolution"
    codec = probe.get("codec_name", "")
    width = probe.get("width")
    height = probe.get("height")

    if not width or not height:
        details = {"codec": codec, "width": width, "height": height}
        return CheckResult(name, Status.FAIL, "Could not read width/height from ffprobe", details)

    ratio = width / height
    matched = next(
        (label for label, expected in _ALLOWED_RATIOS.items() if abs(ratio - expected) <= _RATIO_TOLERANCE),
        None,
    )
    details = {
        "codec": codec,
        "width": width,
        "height": height,
        "aspect_ratio": round(ratio, 4),
        "matched_ratio": matched,
    }

    issues = []
    if codec not in _ALLOWED_CODECS:
        issues.append(f"Codec '{codec}' is not H.264/H.265")
    if matched is None:
        issues.append(f"Aspect ratio {width}:{height} ({ratio:.3f}) doesn't match 9:16, 1:1, or 16:9")

    if issues:
        return CheckResult(name, Status.WARN, "; ".join(issues), details)
    return CheckResult(name, Status.PASS, f"codec={codec}, {width}x{height} ({matched})", details)


def check_blackframes(path: str, thresholds: dict) -> CheckResult:
    name = "blackframes"
    cfg = thresholds["blackdetect"]
    window_seconds = cfg["window_seconds"]

    try:
        start_stderr = ff.run_blackdetect(path, thresholds, "start")
        end_stderr = ff.run_blackdetect(path, thresholds, "end")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        return _ffmpeg_skip_result(name, e)

    def analyze(stderr: str, label: str):
        intervals = ff.parse_blackdetect_output(stderr)
        covered = sum(i["duration"] for i in intervals)
        if covered <= 0:
            status, msg = Status.PASS, f"{label}: no black frames"
        elif covered >= window_seconds * cfg["fail_black_ratio"]:
            status, msg = Status.FAIL, f"{label}: {window_seconds}s window covered by black frames ({covered:.2f}s)"
        else:
            status, msg = Status.WARN, f"{label}: black frames detected in part of the window ({covered:.2f}s / {window_seconds}s)"
        return status, msg, {"covered_seconds": round(covered, 3), "intervals": intervals}

    start_status, start_msg, start_detail = analyze(start_stderr, "Start")
    end_status, end_msg, end_detail = analyze(end_stderr, "End")

    details = {"window_seconds": window_seconds, "start": start_detail, "end": end_detail}
    return CheckResult(name, worst_status(start_status, end_status), f"{start_msg}; {end_msg}", details)


def check_freeze(path: str, thresholds: dict) -> CheckResult:
    name = "freeze"
    cfg = thresholds["freezedetect"]

    try:
        stderr = ff.run_freezedetect(path, thresholds)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        return _ffmpeg_skip_result(name, e)

    intervals = ff.parse_freezedetect_output(stderr)
    if not intervals:
        return CheckResult(name, Status.PASS, "No freeze detected", {"intervals": []})

    unresolved = [i for i in intervals if i["duration"] is None]
    if unresolved:
        start = unresolved[0]["start"]
        message = f"Frozen from {start:.2f}s and never recovers before the clip ends"
        return CheckResult(name, Status.FAIL, message, {"intervals": intervals, "unresolved": True})

    longest = max(i["duration"] for i in intervals)
    details = {"intervals": intervals, "longest_duration": longest, "unresolved": False}
    if longest >= cfg["fail_duration"]:
        message = f"{len(intervals)} freeze interval(s) detected, longest {longest:.2f}s (FAIL threshold: {cfg['fail_duration']}s)"
        return CheckResult(name, Status.FAIL, message, details)
    return CheckResult(name, Status.WARN, f"{len(intervals)} freeze interval(s) detected, longest {longest:.2f}s", details)


def check_loudness(path: str, thresholds: dict) -> CheckResult:
    name = "loudness"
    loud_cfg = thresholds["loudness"]
    clip_cfg = thresholds["clipping"]

    try:
        ebur_stderr = ff.run_ebur128(path)
        astats_stderr = ff.run_astats(path)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        return _ffmpeg_skip_result(name, e)

    loudness = ff.parse_ebur128_output(ebur_stderr)
    clipping = ff.parse_astats_output(astats_stderr)

    issues = []
    statuses = [Status.PASS]

    integrated = loudness.get("integrated_lufs")
    if integrated is None:
        issues.append("Could not measure integrated loudness (LUFS)")
        statuses.append(Status.WARN)
    elif integrated < loud_cfg["min_integrated_lufs"]:
        issues.append(f"Integrated loudness {integrated:.1f} LUFS (below {loud_cfg['min_integrated_lufs']} LUFS threshold — too quiet)")
        statuses.append(Status.WARN)
    else:
        issues.append(f"Integrated loudness {integrated:.1f} LUFS")

    peak_db = clipping.get("peak_level_db")
    if peak_db is not None and peak_db >= clip_cfg["near_zero_peak_db"]:
        issues.append(f"Possible clipping (peak {peak_db:.2f}dB, at/above {clip_cfg['near_zero_peak_db']}dB near 0dBFS)")
        statuses.append(Status.WARN)
    else:
        issues.append("No clipping detected")

    details = {
        "integrated_lufs": integrated,
        "true_peak_dbfs": loudness.get("true_peak_dbfs"),
        "min_integrated_lufs": loud_cfg["min_integrated_lufs"],
        "peak_level_db": peak_db,
        "near_zero_peak_db": clip_cfg["near_zero_peak_db"],
    }
    return CheckResult(name, worst_status(*statuses), "; ".join(issues), details)
