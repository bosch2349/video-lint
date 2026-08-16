# video-lint

[English](README.md) | [简体中文](README.zh-CN.md) | [한국어](README.ko.md)

[![Tests](https://github.com/bosch2349/video-lint/actions/workflows/test.yml/badge.svg)](https://github.com/bosch2349/video-lint/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/bosch2349/video-lint)](https://github.com/bosch2349/video-lint/releases)

A local QA CLI for AI-generated short-form videos (TikTok/YouTube Shorts/Reels) — run it before you publish.

> ⚠️ **Safe zone / threshold values are still unverified engineering estimates** (`safe_zones.json` / `thresholds.json`, `"verified": false`). The CLI prints a warning on every run. See [Safe Zone Confidence](#safe-zone-confidence) for the rationale and current confidence level.

## Why video-lint?

When you generate short-form video quickly with AI, the problems that ruin a post often only show up right before (or after) you hit publish:

- The first frame renders black
- The video freezes mid-clip or at the end
- Audio is too quiet, or clipping
- Captions overlap the platform's UI (like/comment buttons, caption area)
- Wrong aspect ratio or codec

video-lint catches these locally, before upload. No server, no upload — everything runs through ffmpeg on your machine.

## Features

| Check | Description |
|---|---|
| `codec/resolution` | Aspect ratio (9:16/1:1/16:9) and codec (H.264/H.265) check |
| `blackframes` | Black-frame check at the start/end of the clip |
| `freeze` | Freeze-frame check — also catches freezes that never recover before the clip ends |
| `loudness` | Loudness (LUFS) and clipping check |
| `safe zone` | Caption-overlaps-platform-UI check |

## Quick Start

Install:

```
pip install -e .
```

Run:

```
video-lint sample.mp4
```

JSON (for CI/automation pipelines):

```
video-lint sample.mp4 --json
```

HTML (a report you can open straight in a browser):

```
video-lint sample.mp4 --html report.html
```

## Example Output

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: Start: 1.0s window covered by black frames (0.97s); End: no black frames
[WARN] loudness: Integrated loudness -35.0 LUFS (below -30.0 LUFS threshold — too quiet); No clipping detected
[PASS] freeze: No freeze detected
[SKIP] safe-zone/tiktok: Skipped safe zone check because no subtitle file was given (video may have burned-in captions)
```

Exit code is `1` if any check is `FAIL`, otherwise `0`.

## Project Status

**v0.1 MVP**

Done:
- CLI (human-readable, colorized checklist output)
- `--json` output (for CI/automation pipelines)
- `--html` standalone report
- 5 ffmpeg-based checks (codec/resolution, blackframes, loudness, freeze, safe zone)

Roadmap:
- Verify safe zones against real app screenshots (promote to `confidence: screenshot_verified`)
- Reports with a video preview (thumbnail/timeline)
- AI-generated fix suggestions (e.g. "trim the first 0.97s")

---

Detailed documentation follows below.

## Installation

Requirements: Python 3.11+, ffmpeg/ffprobe (must already be installed on your system — on macOS, `brew install ffmpeg`).

```
git clone https://github.com/bosch2349/video-lint.git
cd video-lint
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Verify the install:

```
video-lint --help
```

Since this is an editable (`-e`) install, code changes during development take effect immediately without reinstalling. See [Testing](#testing) below for how to run the test suite.

## Detailed Usage

```
video-lint <video.mp4> [--subs subtitle.srt|.ass|.ssa] [--platform tiktok|shorts|reels|all] [--font-size PX] [--json] [--html PATH]
```

- `--subs`: For `.ass`/`.ssa`, uses `MarginL`/`MarginR`/`MarginV` and `\pos` tags for exact positioning. `.srt` has no position data, so it assumes "bottom-center rendering" and estimates based on line count/character count.
- Without `--subs`, the safe zone check is `SKIP` (the video may have burned-in captions, which can't be judged without OCR).
- `--font-size`: Explicitly set the font height (px) used for default-aligned SRT/ASS captions. Defaults to an estimate of ~4.5% of the frame height.
- Results use 4 statuses: `PASS`/`WARN`/`FAIL`/`SKIP` (`SKIP` means the check itself couldn't run — ffmpeg missing/failed, or `--subs` not given). Colorized in a TTY terminal; plain text when piped/redirected.
- Exit code: `1` if any check is `FAIL`, otherwise `0`.

## Safe Zone Confidence

The goal of `safe_zones.json` isn't to provide "the correct coordinates" — it's to **track evidence and confidence**. Alongside each platform's `top`/`bottom`/`left`/`right` coordinates, the following fields are recorded:

| Field | Meaning |
|---|---|
| `confidence` | `estimate` (no official fixed spec exists) / `conservative_estimate` (an official number exists, but it's an ads spec, unconfirmed for organic posts) / `screenshot_verified` (measured from a real app screenshot — no platform has reached this stage yet) |
| `source` | Explanation of why this confidence level was assigned |
| `source_url` | Link to the official documentation that was researched |
| `note` | One-line summary |

None of the three platforms turned out to have an official fixed spec we could point to and say "these coordinates are 100% correct":

- **TikTok** (`confidence: estimate`) — [TikTok Ads Manager's official docs](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads) only state that "the safe zone size depends on caption length/ad format," with no fixed numbers. There's no official spec at all for organic (non-ad) video.
- **YouTube Shorts** (`confidence: estimate`) — [YouTube's official Help Center](https://support.google.com/youtube/answer/16215842) explicitly states there are no fixed values; guide lines are shown dynamically in the editor UI instead.
- **Instagram/Facebook Reels** (`confidence: conservative_estimate`) — [Meta's official Ads Help Center](https://www.facebook.com/business/help/980593475366490/) is the only one with concrete numbers (top 14% / bottom 35% / sides 6% each), but that's an ads spec (includes CTA/product-tag overlays), with no guarantee it matches the organic Reels UI — so it's classified one notch down. The Meta numbers are kept for reference in the `ads_safe_zone_reference_1080x1920` field, but are not used in the actual danger-zone judgment.

So `verified: false` was left as-is, and these coordinates will need to be updated whenever a platform's UI changes. The next step is measuring UI element coordinates from real app screenshots and promoting to `confidence: "screenshot_verified"` — that has to be done by a human.

Example human-readable output:

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: Start: 1.0s window covered by black frames (0.97s); End: no black frames
[WARN] loudness: Integrated loudness -35.0 LUFS (below -30.0 LUFS threshold — too quiet); No clipping detected
[PASS] freeze: No freeze detected
[SKIP] safe-zone/tiktok: Skipped safe zone check because no subtitle file was given (video may have burned-in captions)
```

### `--json` output

Prints JSON to stdout that CI/automation pipelines can parse directly. The `[WARNING]` notice shown when `safe_zones.json`/`thresholds.json` are unverified always goes to stderr instead, so it never pollutes stdout — with `--json`, stdout always contains pure JSON only.

```
$ video-lint clip.mp4 --platform tiktok --json
{
  "file": "clip.mp4",
  "overall_status": "FAIL",
  "checks": [
    {
      "name": "codec/resolution",
      "status": "PASS",
      "message": "codec=h264, 1080x1920 (9:16)",
      "details": { "codec": "h264", "width": 1080, "height": 1920, "aspect_ratio": 0.5625, "matched_ratio": "9:16" }
    },
    {
      "name": "blackframes",
      "status": "FAIL",
      "message": "Start: 1.0s window covered by black frames (0.97s); End: no black frames",
      "details": { "window_seconds": 1.0, "start": { "covered_seconds": 0.967, "intervals": [...] }, "end": { "covered_seconds": 0, "intervals": [] } }
    }
  ]
}
```

- `overall_status`: the most severe status among all checks (`FAIL` > `WARN` > `PASS`/`SKIP`).
- `checks[].details`: structured raw data per check (codec/resolution, black-frame intervals, LUFS/clipping numbers, freeze intervals, safe-zone pixel values, etc.) — designed so automation can use it directly instead of regex-scraping `message`.
- `NaN`/`Infinity` values (e.g. LUFS is `-inf` on total silence) aren't valid JSON, so they're replaced with `null` on the way out — safe to read with strict JSON parsers too.
- A fatal ffprobe failure (file not found, ffmpeg missing, etc.) does not produce JSON on stdout even with `--json` — it's reported via a stderr message and exit code `1` only. Pipelines should check the exit code first, and only parse stdout as JSON on 0/1.

### `--html` report

Saves the results as a single, human-friendly, standalone HTML file. No external server/framework/CDN — the CSS is inlined into the one file, so you can just open it in a browser.

```
$ video-lint input.mp4 --html report.html
Report written:
report.html
```

- Doesn't touch the existing check logic, the `CheckResult` structure, or `--json` output at all — `video_lint/report.py` is a separate layer that takes a list of `CheckResult` and turns it into an HTML string. Safe to use together with `--json` (stdout stays pure JSON, HTML is written to a file).
- The `Report written:` notice goes to stderr, not stdout — so it won't pollute stdout even when combined with `--json`.
- Report layout: header (filename / timestamp / overall status) → summary cards counting PASS/WARN/FAIL/SKIP → per-check status table → a details section that expands each check's `details` into human-readable labels (e.g. `covered_seconds` → `Covered Seconds`).
- Exit code is unaffected by `--html` (still `1` if any check is `FAIL`).

### CI example (GitHub Actions)

```yaml
- name: video-lint
  run: |
    video-lint out/final.mp4 --platform all --json > lint-result.json
    status=$(python3 -c "import json;print(json.load(open('lint-result.json'))['overall_status'])")
    echo "overall_status=$status"
    if [ "$status" = "FAIL" ]; then
      echo "::error::video-lint FAIL — see lint-result.json"
      exit 1
    fi
```

Simpler if you have `jq`:

```
video-lint out/final.mp4 --json | jq -e '.overall_status != "FAIL"'
```

## Testing

```
for f in tests/test_*.py; do PYTHONPATH=. python3 "$f"; done
```

Two kinds of tests:

- **Mock tests** (`test_checks.py`, `test_subtitles.py`, `test_ffmpeg_filters.py`, `test_checks_media.py`, `test_cli.py`, `test_report.py`): verify parsing/judgment/report-rendering logic by feeding in sample stderr text or swapping out functions, without ever running ffmpeg for real. Must always pass even without ffmpeg installed.
- **E2E test** (`test_e2e.py`): actually runs the full CLI against synthetic clips that `tests/fixtures/generate.py` builds from ffmpeg `lavfi` sources. Skips silently if ffmpeg/ffprobe isn't available. See [tests/fixtures/README.md](tests/fixtures/README.md) for fixture details.

## License

[MIT](LICENSE)
