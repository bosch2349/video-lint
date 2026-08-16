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
        return CheckResult(name, Status.SKIP, "ffmpeg를 찾을 수 없음 (ffmpeg 설치 여부 확인)")
    return CheckResult(name, Status.SKIP, f"ffmpeg 실행 실패로 체크를 건너뜀: {error}")


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
        return CheckResult(name, Status.FAIL, "ffprobe에서 width/height를 읽지 못함", details)

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
        issues.append(f"코덱 '{codec}'은 H.264/H.265가 아님")
    if matched is None:
        issues.append(f"비율 {width}:{height} ({ratio:.3f})이 9:16/1:1/16:9 어디에도 해당 안 됨")

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
            status, msg = Status.PASS, f"{label} 블랙프레임 없음"
        elif covered >= window_seconds * cfg["fail_black_ratio"]:
            status, msg = Status.FAIL, f"{label} {window_seconds}초 구간이 블랙프레임으로 덮임 ({covered:.2f}s)"
        else:
            status, msg = Status.WARN, f"{label} 일부 구간에 블랙프레임 감지됨 ({covered:.2f}s / {window_seconds}s)"
        return status, msg, {"covered_seconds": round(covered, 3), "intervals": intervals}

    start_status, start_msg, start_detail = analyze(start_stderr, "시작")
    end_status, end_msg, end_detail = analyze(end_stderr, "끝")

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
        return CheckResult(name, Status.PASS, "정지 구간 없음", {"intervals": []})

    unresolved = [i for i in intervals if i["duration"] is None]
    if unresolved:
        start = unresolved[0]["start"]
        message = f"{start:.2f}s부터 영상이 끝날 때까지 정지 상태에서 회복되지 않음"
        return CheckResult(name, Status.FAIL, message, {"intervals": intervals, "unresolved": True})

    longest = max(i["duration"] for i in intervals)
    details = {"intervals": intervals, "longest_duration": longest, "unresolved": False}
    if longest >= cfg["fail_duration"]:
        message = f"{len(intervals)}개 정지 구간 감지, 최대 {longest:.2f}s (기준 {cfg['fail_duration']}s 이상 FAIL)"
        return CheckResult(name, Status.FAIL, message, details)
    return CheckResult(name, Status.WARN, f"{len(intervals)}개 정지 구간 감지, 최대 {longest:.2f}s", details)


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
        issues.append("통합 음량(LUFS)을 측정하지 못함")
        statuses.append(Status.WARN)
    elif integrated < loud_cfg["min_integrated_lufs"]:
        issues.append(f"통합 음량 {integrated:.1f} LUFS (기준 {loud_cfg['min_integrated_lufs']} LUFS 미만 — 너무 조용함)")
        statuses.append(Status.WARN)
    else:
        issues.append(f"통합 음량 {integrated:.1f} LUFS")

    peak_db = clipping.get("peak_level_db")
    if peak_db is not None and peak_db >= clip_cfg["near_zero_peak_db"]:
        issues.append(f"클리핑 의심 (peak {peak_db:.2f}dB, 0dBFS 기준 {clip_cfg['near_zero_peak_db']}dB 이상)")
        statuses.append(Status.WARN)
    else:
        issues.append("클리핑 미검출")

    details = {
        "integrated_lufs": integrated,
        "true_peak_dbfs": loudness.get("true_peak_dbfs"),
        "min_integrated_lufs": loud_cfg["min_integrated_lufs"],
        "peak_level_db": peak_db,
        "near_zero_peak_db": clip_cfg["near_zero_peak_db"],
    }
    return CheckResult(name, worst_status(*statuses), "; ".join(issues), details)
