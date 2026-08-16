import re
import subprocess

_BLACK_RE = re.compile(
    r"black_start:(?P<start>[\d.]+)\s+black_end:(?P<end>[\d.]+)\s+black_duration:(?P<duration>[\d.]+)"
)
_FREEZE_START_RE = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_DURATION_RE = re.compile(r"freeze_duration:\s*([\d.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:\s*([\d.]+)")
_INTEGRATED_RE = re.compile(r"Integrated loudness:\s*I:\s*(-?[\d.]+|-inf)\s*LUFS")
_TRUE_PEAK_RE = re.compile(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf)\s*dBFS")
_PEAK_LEVEL_RE = re.compile(r"Peak level dB:\s*(-?[\d.]+|-inf)")
_PEAK_COUNT_RE = re.compile(r"Peak count:\s*([\d.]+)")
_NUM_SAMPLES_RE = re.compile(r"Number of samples:\s*([\d.]+)")


def _run(cmd: list) -> str:
    """ffmpeg 필터 로그는 stderr로 나오므로 stderr 텍스트를 반환한다."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stderr


def run_blackdetect(path: str, thresholds: dict, window: str) -> str:
    """window: 'start' 또는 'end' — 영상 시작/끝 구간에 blackdetect 필터 적용."""
    cfg = thresholds["blackdetect"]
    filter_expr = f"blackdetect=d={cfg['d']}:pic_th={cfg['pic_th']}:pix_th={cfg['pix_th']}"
    seek = ["-t", str(cfg["window_seconds"])] if window == "start" else ["-sseof", f"-{cfg['window_seconds']}"]
    cmd = ["ffmpeg", "-hide_banner", *seek, "-i", path, "-vf", filter_expr, "-an", "-f", "null", "-"]
    return _run(cmd)


def run_freezedetect(path: str, thresholds: dict) -> str:
    cfg = thresholds["freezedetect"]
    filter_expr = f"freezedetect=n={cfg['n']}:d={cfg['d']}"
    cmd = ["ffmpeg", "-hide_banner", "-i", path, "-vf", filter_expr, "-an", "-f", "null", "-"]
    return _run(cmd)


def run_ebur128(path: str) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"]
    return _run(cmd)


def run_astats(path: str) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-i", path, "-af", "astats", "-vn", "-f", "null", "-"]
    return _run(cmd)


def parse_blackdetect_output(stderr: str) -> list:
    return [
        {"start": float(m["start"]), "end": float(m["end"]), "duration": float(m["duration"])}
        for m in _BLACK_RE.finditer(stderr)
    ]


def parse_freezedetect_output(stderr: str) -> list:
    """영상이 끝날 때까지 정지 상태가 회복되지 않으면 ffmpeg가 freeze_duration/freeze_end를
    아예 찍지 않는다 (실측으로 확인됨) — 그 경우 duration/end를 None으로 남겨 미종결 상태를 표시한다."""
    starts = [float(x) for x in _FREEZE_START_RE.findall(stderr)]
    durations = [float(x) for x in _FREEZE_DURATION_RE.findall(stderr)]
    ends = [float(x) for x in _FREEZE_END_RE.findall(stderr)]

    intervals = [{"start": s, "duration": d, "end": e} for s, d, e in zip(starts, durations, ends)]
    if len(starts) > len(durations):
        intervals.append({"start": starts[-1], "duration": None, "end": None})
    return intervals


def _to_float_or_neg_inf(value: str) -> float:
    return float("-inf") if value == "-inf" else float(value)


def parse_ebur128_output(stderr: str) -> dict:
    """ffmpeg ebur128 필터의 Summary 블록에서 통합 음량/트루피크를 읽는다."""
    integrated_match = _INTEGRATED_RE.search(stderr)
    peak_match = _TRUE_PEAK_RE.search(stderr)
    return {
        "integrated_lufs": _to_float_or_neg_inf(integrated_match.group(1)) if integrated_match else None,
        "true_peak_dbfs": _to_float_or_neg_inf(peak_match.group(1)) if peak_match else None,
    }


def parse_astats_output(stderr: str) -> dict:
    """astats는 채널별 블록 뒤에 Overall 집계 블록을 출력하므로 마지막(=Overall) 값을 사용한다."""
    peak_matches = _PEAK_LEVEL_RE.findall(stderr)
    count_matches = _PEAK_COUNT_RE.findall(stderr)
    sample_matches = _NUM_SAMPLES_RE.findall(stderr)

    peak_db = _to_float_or_neg_inf(peak_matches[-1]) if peak_matches else None
    peak_count = float(count_matches[-1]) if count_matches else None
    num_samples = float(sample_matches[-1]) if sample_matches else None
    clipped_ratio = (peak_count / num_samples) if peak_count is not None and num_samples else None

    return {
        "peak_level_db": peak_db,
        "peak_count": peak_count,
        "num_samples": num_samples,
        "clipped_ratio": clipped_ratio,
    }
