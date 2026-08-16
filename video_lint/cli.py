import argparse
import json
import math
import subprocess
import sys

from .checks import (
    Status,
    check_blackframes,
    check_codec_resolution,
    check_freeze,
    check_loudness,
    load_thresholds,
    worst_status,
)
from .ffprobe import probe_video
from .subtitles import check_safe_zone, load_safe_zones

_PLATFORMS = ["tiktok", "shorts", "reels"]

_COLORS = {
    Status.PASS: "\033[32m",
    Status.WARN: "\033[33m",
    Status.FAIL: "\033[31m",
    Status.SKIP: "\033[90m",
}
_RESET = "\033[0m"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-lint",
        description="숏폼 영상(TikTok/Shorts/Reels) 게시 전 로컬 QA 체크 도구",
    )
    parser.add_argument("video", help="검사할 영상 파일 경로")
    parser.add_argument("--subs", help="자막 파일 경로 (.srt/.ass/.ssa)")
    parser.add_argument(
        "--platform",
        choices=[*_PLATFORMS, "all"],
        default="all",
        help="대상 플랫폼 (기본: all)",
    )
    parser.add_argument(
        "--font-size",
        type=float,
        default=None,
        help="SRT/ASS 기본 정렬 자막의 폰트 높이(px) 직접 지정 (기본: 화면 높이의 약 4.5%%로 추정)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="사람이 보는 체크리스트 대신 JSON으로 출력 (CI/자동화 파이프라인용)",
    )
    return parser


def _format_status(status: Status) -> str:
    label = f"[{status.value}]"
    if not sys.stdout.isatty():
        return label
    return f"{_COLORS[status]}{label}{_RESET}"


def _print_human(results: list) -> None:
    for result in results:
        print(f"{_format_status(result.status)} {result.name}: {result.message}")


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _to_json(video_path: str, results: list, overall: Status) -> str:
    payload = {
        "file": video_path,
        "overall_status": overall.value,
        "checks": [
            {
                "name": r.name,
                "status": r.status.value,
                "message": r.message,
                "details": _json_safe(r.details),
            }
            for r in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        probe = probe_video(args.video)
    except FileNotFoundError:
        print("오류: ffprobe를 찾을 수 없음 (ffmpeg 설치 여부 확인)", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"오류: ffprobe 실행 실패 - {e.stderr.strip()}", file=sys.stderr)
        return 1

    zones_config = load_safe_zones()
    thresholds = load_thresholds()
    for filename, cfg in (("safe_zones.json", zones_config), ("thresholds.json", thresholds)):
        if not cfg.get("verified", True):
            # --json 출력(stdout)을 오염시키지 않도록 경고는 항상 stderr로 보낸다.
            print(f"[WARNING] {filename}: {cfg['note']}", file=sys.stderr)

    results = [
        check_codec_resolution(probe),
        check_blackframes(args.video, thresholds),
        check_loudness(args.video, thresholds),
        check_freeze(args.video, thresholds),
    ]

    platforms = _PLATFORMS if args.platform == "all" else [args.platform]
    for platform in platforms:
        results.append(check_safe_zone(args.subs, platform, zones_config, args.font_size))

    overall = worst_status(*(r.status for r in results))

    if args.json:
        print(_to_json(args.video, results, overall))
    else:
        _print_human(results)

    return 1 if overall == Status.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
