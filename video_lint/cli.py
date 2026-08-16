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
from .report import write_html_report
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
        description="Local QA CLI for short-form videos (TikTok/Shorts/Reels) before you publish",
    )
    parser.add_argument("video", help="Path to the video file to check")
    parser.add_argument("--subs", help="Subtitle file path (.srt/.ass/.ssa)")
    parser.add_argument(
        "--platform",
        choices=[*_PLATFORMS, "all"],
        default="all",
        help="Target platform (default: all)",
    )
    parser.add_argument(
        "--font-size",
        type=float,
        default=None,
        help="Explicit font height (px) for default-aligned SRT/ASS captions (default: estimated as ~4.5%% of frame height)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of the human-readable checklist (for CI/automation pipelines)",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        default=None,
        help="Save results as a human-friendly standalone HTML file (e.g. --html report.html)",
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
        print("Error: ffprobe not found (check that ffmpeg is installed)", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Error: ffprobe execution failed - {e.stderr.strip()}", file=sys.stderr)
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

    if args.html:
        write_html_report(args.video, results, overall, args.html)
        # --json 출력(stdout)을 오염시키지 않도록 이 알림도 stderr로 보낸다.
        print(f"Report written:\n{args.html}", file=sys.stderr)

    return 1 if overall == Status.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
