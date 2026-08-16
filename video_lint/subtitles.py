import json
import math
import re
from pathlib import Path

from .checks import CheckResult, Status

DEFAULT_SAFE_ZONES_PATH = Path(__file__).parent / "safe_zones.json"

_POS_RE = re.compile(r"\\pos\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_ASS_TAG_RE = re.compile(r"\{[^}]*\}")
_SRT_BLOCK_RE = re.compile(r"\n\s*\n")
_SRT_TIME_RE = re.compile(r"-->")

# 아래 세 상수는 실측 폰트 렌더링 데이터가 아닌 경험적 추정치. --font-size로 폰트 높이는 오버라이드 가능.
DEFAULT_FONT_SIZE_RATIO = 0.045  # 화면 높이 대비 기본 폰트 높이 추정 비율
_AVG_CHAR_WIDTH_RATIO = 0.6      # 폰트 높이 대비 평균 글자 폭 추정 비율
_TEXT_BLOCK_WIDTH_FRACTION = 0.9  # 자막 블록이 차지한다고 가정하는 화면 폭 비율

SRT_ESTIMATE_DISCLAIMER = (
    "⚠ 추정치 (SRT는 실제 위치 정보 없음, 편집기에서 직접 위치를 옮겼다면 부정확할 수 있음)"
)


def load_safe_zones(config_path: Path | None = None) -> dict:
    with open(config_path or DEFAULT_SAFE_ZONES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _zone_details(zone: dict) -> dict:
    return {
        "top": zone["top"],
        "bottom": zone["bottom"],
        "left": zone["left"],
        "right": zone["right"],
        "ref_width": zone["ref_width"],
        "ref_height": zone["ref_height"],
    }


# --- 좌표 판정 (rect = (left, top, right, bottom), band도 동일 형식) ---


def _rect_status(rect: tuple, band: tuple) -> str:
    l, t, r, b = rect
    bl, bt, br, bb = band
    if l == r and t == b:  # \pos 앵커처럼 면적이 없는 점
        return "full" if (bl <= l <= br and bt <= t <= bb) else "none"
    ix_l, ix_r = max(l, bl), min(r, br)
    iy_t, iy_b = max(t, bt), min(b, bb)
    if ix_l >= ix_r or iy_t >= iy_b:
        return "none"
    if bl <= l and br >= r and bt <= t and bb >= b:
        return "full"
    return "partial"


def _danger_bands(zone: dict) -> list:
    w, h = zone["ref_width"], zone["ref_height"]
    bands = []
    if zone.get("top"):
        bands.append((0, 0, w, zone["top"]))
    if zone.get("bottom"):
        bands.append((0, h - zone["bottom"], w, h))
    if zone.get("left"):
        bands.append((0, 0, zone["left"], h))
    if zone.get("right"):
        bands.append((w - zone["right"], 0, w, h))
    return bands


def classify_rect(rect: tuple, zone: dict) -> Status:
    worst = "none"
    for band in _danger_bands(zone):
        state = _rect_status(rect, band)
        if state == "full":
            return Status.FAIL
        if state == "partial":
            worst = "partial"
    return Status.WARN if worst == "partial" else Status.PASS


# --- 텍스트 줄 수 x 폰트 높이 -> 렌더 높이 추정 ---


def estimate_text_block_height(lines: list, ref_width: int, font_height_px: float) -> float:
    chars_per_line = max(1, int((ref_width * _TEXT_BLOCK_WIDTH_FRACTION) / (font_height_px * _AVG_CHAR_WIDTH_RATIO)))
    total_lines = sum(math.ceil(len(line) / chars_per_line) if line else 1 for line in lines) or 1
    return total_lines * font_height_px


# --- ASS/SSA ---


def _parse_script_resolution(content: str) -> tuple:
    x_match = re.search(r"(?im)^PlayResX:\s*(\d+)", content)
    y_match = re.search(r"(?im)^PlayResY:\s*(\d+)", content)
    play_x = int(x_match.group(1)) if x_match else 1080
    play_y = int(y_match.group(1)) if y_match else 1920
    return play_x, play_y


def _parse_ass_events(content: str) -> list:
    in_events = False
    format_fields: list = []
    cues = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_events = line.lower() == "[events]"
            continue
        if not in_events:
            continue
        if line.lower().startswith("format:"):
            format_fields = [f.strip().lower() for f in line.split(":", 1)[1].split(",")]
            continue
        if line.lower().startswith("dialogue:") and format_fields:
            values = [v.strip() for v in line.split(":", 1)[1].split(",", len(format_fields) - 1)]
            if len(values) == len(format_fields):
                cues.append(dict(zip(format_fields, values)))
    return cues


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def check_ass_safe_zone(content: str, zone: dict, font_size_px: float = None) -> CheckResult:
    play_x, play_y = _parse_script_resolution(content)
    ref_w, ref_h = zone["ref_width"], zone["ref_height"]
    scale_x, scale_y = ref_w / play_x, ref_h / play_y

    cues = _parse_ass_events(content)
    if not cues:
        details = {"platform": zone["platform"], "format": "ass", "danger_zone": _zone_details(zone)}
        return CheckResult(f"safe-zone/{zone['platform']}", Status.WARN, "ASS 파일에서 Dialogue 라인을 찾지 못함", details)

    font_height = font_size_px or ref_h * DEFAULT_FONT_SIZE_RATIO

    fail = warn = 0
    for cue in cues:
        text = cue.get("text", "")
        pos_match = _POS_RE.search(text)
        if pos_match:
            x, y = float(pos_match.group(1)) * scale_x, float(pos_match.group(2)) * scale_y
            rect = (x, y, x, y)
        else:
            margin_l = _to_float(cue.get("marginl")) * scale_x
            margin_r = _to_float(cue.get("marginr")) * scale_x
            margin_v = _to_float(cue.get("marginv")) * scale_y
            plain = _ASS_TAG_RE.sub("", text).replace("\\N", "\n").replace("\\n", "\n")
            lines = plain.splitlines() or [""]
            height = estimate_text_block_height(lines, ref_w, font_height)
            bottom = ref_h - margin_v
            rect = (margin_l, bottom - height, ref_w - margin_r, bottom)

        status = classify_rect(rect, zone)
        fail += status == Status.FAIL
        warn += status == Status.WARN

    total = len(cues)
    overall = Status.FAIL if fail else Status.WARN if warn else Status.PASS
    message = (
        f"자막 {total}개 중 FAIL {fail}개, WARN {warn}개 "
        f"(danger zone: top={zone['top']}px bottom={zone['bottom']}px left={zone['left']}px right={zone['right']}px, "
        f"기준해상도 {ref_w}x{ref_h})"
    )
    details = {
        "platform": zone["platform"],
        "format": "ass",
        "total": total,
        "fail_count": fail,
        "warn_count": warn,
        "danger_zone": _zone_details(zone),
        "estimated": False,
    }
    return CheckResult(f"safe-zone/{zone['platform']}", overall, message, details)


# --- SRT ---


def _parse_srt_cues(content: str) -> list:
    texts = []
    for block in _SRT_BLOCK_RE.split(content.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        text_lines = [l for l in lines if not l.strip().isdigit() and not _SRT_TIME_RE.search(l)]
        if text_lines:
            texts.append("\n".join(text_lines))
    return texts


def check_srt_safe_zone(content: str, zone: dict, font_size_px: float = None) -> CheckResult:
    cues = _parse_srt_cues(content)
    if not cues:
        details = {"platform": zone["platform"], "format": "srt", "danger_zone": _zone_details(zone)}
        return CheckResult(f"safe-zone/{zone['platform']}", Status.WARN, "SRT 파일에서 자막 큐를 찾지 못함", details)

    ref_w, ref_h = zone["ref_width"], zone["ref_height"]
    font_height = font_size_px or ref_h * DEFAULT_FONT_SIZE_RATIO
    left = ref_w * (1 - _TEXT_BLOCK_WIDTH_FRACTION) / 2
    right = ref_w - left

    fail = warn = 0
    for text in cues:
        lines = text.splitlines() or [""]
        height = estimate_text_block_height(lines, ref_w, font_height)
        rect = (left, ref_h - height, right, ref_h)  # 기본 렌더링 = 하단중앙 가정
        status = classify_rect(rect, zone)
        fail += status == Status.FAIL
        warn += status == Status.WARN

    total = len(cues)
    overall = Status.FAIL if fail else Status.WARN if warn else Status.PASS
    message = (
        f"자막 {total}개 중 FAIL {fail}개, WARN {warn}개 "
        f"(danger zone: top={zone['top']}px bottom={zone['bottom']}px left={zone['left']}px right={zone['right']}px, "
        f"기준해상도 {ref_w}x{ref_h}, 폰트 높이 추정 {font_height:.0f}px) — {SRT_ESTIMATE_DISCLAIMER}"
    )
    details = {
        "platform": zone["platform"],
        "format": "srt",
        "total": total,
        "fail_count": fail,
        "warn_count": warn,
        "danger_zone": _zone_details(zone),
        "estimated": True,
        "estimated_font_height_px": round(font_height, 1),
    }
    return CheckResult(f"safe-zone/{zone['platform']}", overall, message, details)


# --- 진입점 ---


def check_safe_zone(subs_path, platform: str, zones_config: dict, font_size_px: float = None) -> CheckResult:
    if subs_path is None:
        return CheckResult(
            f"safe-zone/{platform}",
            Status.SKIP,
            "자막 파일을 안 줘서 safe zone 체크를 건너뜀 (burned-in 자막일 수 있음)",
            {"platform": platform},
        )

    platform_zone = zones_config["platforms"][platform]
    zone = {
        "platform": platform,
        "ref_width": zones_config["reference_resolution"]["width"],
        "ref_height": zones_config["reference_resolution"]["height"],
        **platform_zone,
    }

    path = Path(subs_path)
    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if suffix in (".ass", ".ssa"):
        return check_ass_safe_zone(content, zone, font_size_px)
    if suffix == ".srt":
        return check_srt_safe_zone(content, zone, font_size_px)
    details = {"platform": platform, "format": suffix.lstrip(".")}
    return CheckResult(f"safe-zone/{platform}", Status.WARN, f"지원하지 않는 자막 포맷: {suffix}", details)
