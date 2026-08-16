# video-lint

[English](README.md) | [简体中文](README.zh-CN.md) | [한국어](README.ko.md)

[![Tests](https://github.com/bosch2349/video-lint/actions/workflows/test.yml/badge.svg)](https://github.com/bosch2349/video-lint/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/bosch2349/video-lint)](https://github.com/bosch2349/video-lint/releases)

一个本地 QA CLI 工具，用于在发布前检查 AI 生成的短视频（TikTok/YouTube Shorts/Reels）。

> ⚠️ **safe zone / 判定阈值目前仍是未经验证的工程估计值**（`safe_zones.json`/`thresholds.json`，`"verified": false`）。每次运行 CLI 都会打印警告。依据和可信度详情见 [Safe Zone 可信度](#safe-zone-可信度)。

## 为什么用 video-lint？

用 AI 快速生成短视频时，很多问题往往要到上传前（甚至上传后）才会被发现：

- 第一帧是黑屏
- 视频中途或结尾卡住（freeze）
- 音量过小，或存在削波（clipping）
- 字幕挡住了平台 UI（点赞/评论按钮、字幕区域）
- 画面比例或编码格式不对

video-lint 会在上传前，在本地自动检查这些问题。无服务器、无上传 —— 全部依赖 ffmpeg 在本地处理。

## 功能特性

| 检查项 | 说明 |
|---|---|
| `codec/resolution` | 画面比例（9:16/1:1/16:9）、编码（H.264/H.265）检查 |
| `blackframes` | 开头/结尾黑屏检查 |
| `freeze` | 卡顿（freeze）区间检查 —— 也能检测出直到结尾都没恢复的卡顿 |
| `loudness` | 音量（LUFS）、削波检查 |
| `safe zone` | 字幕是否侵占平台 UI 区域的检查 |

## 快速开始

安装：

```
pip install -e .
```

运行：

```
video-lint sample.mp4
```

JSON（用于 CI/自动化流水线）：

```
video-lint sample.mp4 --json
```

HTML（可直接在浏览器打开的报告）：

```
video-lint sample.mp4 --html report.html
```

## 输出示例

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: Start: 1.0s window covered by black frames (0.97s); End: no black frames
[WARN] loudness: Integrated loudness -35.0 LUFS (below -30.0 LUFS threshold — too quiet); No clipping detected
[PASS] freeze: No freeze detected
[SKIP] safe-zone/tiktok: Skipped safe zone check because no subtitle file was given (video may have burned-in captions)
```

只要有一项 `FAIL`，退出码就是 `1`，否则是 `0`。

## 项目状态

**v0.1 MVP**

已完成：
- CLI（带颜色的人类可读检查清单输出）
- `--json` 输出（用于 CI/自动化流水线）
- `--html` 独立报告
- 5 项基于 ffmpeg 的检查（codec/resolution、blackframes、loudness、freeze、safe zone）

Roadmap：
- 基于真实 App 截图验证 safe zone（升级到 `confidence: screenshot_verified`）
- 报告中加入视频预览（缩略图/时间轴）
- AI 驱动的修复建议（例如"建议裁掉开头 0.97 秒"）

---

以下是详细文档。

## 安装

依赖要求：Python 3.11+、ffmpeg/ffprobe（需提前在系统中装好 —— macOS 上可用 `brew install ffmpeg`）。

```
git clone https://github.com/bosch2349/video-lint.git
cd video-lint
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

验证安装：

```
video-lint --help
```

因为是可编辑（`-e`）安装，开发时改代码无需重新安装即可生效。测试运行方式见下方 [测试](#测试) 一节。

## 详细用法

```
video-lint <video.mp4> [--subs subtitle.srt|.ass|.ssa] [--platform tiktok|shorts|reels|all] [--font-size PX] [--json] [--html PATH]
```

- `--subs`：`.ass`/`.ssa` 会用 `MarginL`/`MarginR`/`MarginV` 和 `\pos` 标签精确判定位置。`.srt` 没有位置信息，因此假设"底部居中渲染"，再用行数/字符数估算。
- 不传 `--subs` 时，safe zone 检查会是 `SKIP`（视频可能是烧录字幕，没有 OCR 无法判断）。
- `--font-size`：直接指定默认对齐字幕的字体高度（px）。默认按屏幕高度的约 4.5% 估算。
- 结果状态共 4 种：`PASS`/`WARN`/`FAIL`/`SKIP`（`SKIP` 表示检查本身没跑起来 —— ffmpeg 未安装/执行失败，或没传 `--subs`）。在终端（TTY）里会带颜色显示，管道/重定向时输出纯文本。
- 退出码：只要有一项 `FAIL` 就是 `1`，否则是 `0`。

## Safe Zone 可信度

`safe_zones.json` 的目标不是"提供标准答案坐标"，而是 **管理依据和可信度**。每个平台的 `top`/`bottom`/`left`/`right` 坐标旁边，都会记录以下字段：

| 字段 | 含义 |
|---|---|
| `confidence` | `estimate`（没有官方固定 spec） / `conservative_estimate`（有官方数值，但是广告场景的，未在 organic 内容上确认过） / `screenshot_verified`（用真实 App 截图实测过 —— 目前还没有任何平台达到这个阶段） |
| `source` | 为什么给这个可信度等级的说明 |
| `source_url` | 调研到的官方文档链接 |
| `note` | 一行摘要 |

调研发现，三个平台都没有一份可以拍板"这个坐标 100% 正确"的官方固定 spec：

- **TikTok**（`confidence: estimate`）—— [TikTok Ads Manager 官方文档](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads) 也只是说明"safe zone 大小取决于文案长度/广告格式"，没有固定数值。针对 organic（非广告）视频，压根没有官方 spec。
- **YouTube Shorts**（`confidence: estimate`）—— [YouTube 官方帮助中心](https://support.google.com/youtube/answer/16215842) 明确表示没有固定数值，而是在编辑 UI 里动态显示参考线。
- **Instagram/Facebook Reels**（`confidence: conservative_estimate`）—— [Meta 官方广告帮助中心](https://www.facebook.com/business/help/980593475366490/) 是三者中唯一给出具体数值的（上 14% / 下 35% / 左右各 6%），但这是广告场景（含 CTA/商品标签遮挡）的标准，无法保证和 organic Reels UI 完全一致，因此降一级分类。Meta 的数值仅作为参考保留在 `ads_safe_zone_reference_1080x1920` 字段中，不参与实际的 danger zone 判定。

所以 `verified: false` 保持不变，以后平台 UI 一变，这些坐标也要跟着更新。下一步是打开真实 App，用截图实测 UI 元素坐标，再升级到 `confidence: "screenshot_verified"` —— 这一步必须由人工完成。

人类可读的默认输出示例：

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: Start: 1.0s window covered by black frames (0.97s); End: no black frames
[WARN] loudness: Integrated loudness -35.0 LUFS (below -30.0 LUFS threshold — too quiet); No clipping detected
[PASS] freeze: No freeze detected
[SKIP] safe-zone/tiktok: Skipped safe zone check because no subtitle file was given (video may have burned-in captions)
```

### `--json` 输出

向 stdout 输出可被 CI/自动化流水线直接解析的 JSON。当 `safe_zones.json`/`thresholds.json` 处于未验证状态时弹出的 `[WARNING]` 提示，始终发往 stderr，不会污染 stdout —— 也就是说用 `--json` 时，stdout 永远只包含纯 JSON。

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

- `overall_status`：所有检查中最严重的状态（`FAIL` > `WARN` > `PASS`/`SKIP`）。
- `checks[].details`：每项检查的结构化原始数据（编码/分辨率、黑屏区间、LUFS/削波数值、卡顿区间、safe zone 像素值等）—— 设计目的是让自动化流程直接使用，不必用正则从 `message` 里抠数据。
- `NaN`/`Infinity`（例如完全静音时 LUFS 为 `-inf`）不是合法 JSON，输出时会替换为 `null` —— 严格的 JSON 解析器也能安全读取。
- ffprobe 本身失败的致命错误（文件不存在、ffmpeg 未安装等），即使加了 `--json` 也不会在 stdout 生成 JSON，只会通过 stderr 消息 + 退出码 `1` 通知。流水线应先检查退出码，只有在 0/1 时才把 stdout 当 JSON 解析。

### `--html` 报告

把结果保存为一个人类友好、独立（standalone）的 HTML 文件。没有外部服务器/框架/CDN —— CSS 全部内联在这一个文件里，直接用浏览器打开即可。

```
$ video-lint input.mp4 --html report.html
Report written:
report.html
```

- 完全不影响现有的检查逻辑、`CheckResult` 结构、`--json` 输出 —— `video_lint/report.py` 是独立的一层，只接收 `CheckResult` 列表并生成 HTML 字符串。可以和 `--json` 同时使用（stdout 仍是纯 JSON，HTML 另存为文件）。
- `Report written:` 提示发往 stderr 而不是 stdout —— 和 `--json` 一起用也不会污染 stdout。
- 报告结构：头部（文件名/检查时间/Overall Status）→ PASS/WARN/FAIL/SKIP 数量汇总卡片 → 每项检查的状态表格 → 把每项检查的 `details` 展开成人类可读标签（例如 `covered_seconds` → `Covered Seconds`）的详情区。
- 退出码不受 `--html` 影响（有 `FAIL` 依然是 `1`）。

### CI 使用示例（GitHub Actions）

```yaml
- name: video-lint
  run: |
    video-lint out/final.mp4 --platform all --json > lint-result.json
    status=$(python3 -c "import json;print(json.load(open('lint-result.json'))['overall_status'])")
    echo "overall_status=$status"
    if [ "$status" = "FAIL" ]; then
      echo "::error::video-lint FAIL — 详见 lint-result.json"
      exit 1
    fi
```

如果有 `jq` 会更简单：

```
video-lint out/final.mp4 --json | jq -e '.overall_status != "FAIL"'
```

## 测试

```
for f in tests/test_*.py; do PYTHONPATH=. python3 "$f"; done
```

分为两类：

- **Mock 测试**（`test_checks.py`、`test_subtitles.py`、`test_ffmpeg_filters.py`、`test_checks_media.py`、`test_cli.py`、`test_report.py`）：不实际运行 ffmpeg，用 stderr 样例文本/函数替换来验证解析、判定、报告渲染逻辑。即使没装 ffmpeg 也必须全部通过。
- **E2E 测试**（`test_e2e.py`）：用 `tests/fixtures/generate.py` 基于 ffmpeg `lavfi` 源生成的合成视频，实际跑一遍完整 CLI 来验证。没有 ffmpeg/ffprobe 时会静默跳过。fixture 详情见 [tests/fixtures/README.md](tests/fixtures/README.md)。

## 许可证

[MIT](LICENSE)
