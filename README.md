# video-lint

[![Tests](https://github.com/bosch2349/video-lint/actions/workflows/test.yml/badge.svg)](https://github.com/bosch2349/video-lint/actions/workflows/test.yml)

AI 생성 숏폼 영상(TikTok/YouTube Shorts/Reels)을 게시 전에 검사하는 로컬 QA CLI.

> ⚠️ **safe zone / 판정 임계값 값은 아직 미검증 엔지니어링 추정치**입니다 (`safe_zones.json`/`thresholds.json`, `"verified": false`). CLI 실행 시마다 경고가 출력됩니다. 근거·신뢰도는 [Safe Zone 신뢰도](#safe-zone-신뢰도) 절 참고.

## Why video-lint?

AI로 영상을 빠르게 만들다 보면 업로드 직전에야 눈에 띄는 문제들이 있습니다:

- 첫 프레임이 검게 나오는 문제
- 영상 중간/끝에서 멈추는(freeze) 문제
- 음량이 너무 작거나 클리핑되는 문제
- 자막이 플랫폼 UI(좋아요·댓글·캡션 영역)와 겹치는 문제
- 잘못된 화면 비율/코덱

video-lint는 이런 문제를 업로드 전에 로컬에서 자동으로 검사합니다. 서버 없음, 업로드 없음 — ffmpeg만으로 전부 로컬 처리.

## Features

| Check | Description |
|---|---|
| `codec/resolution` | 영상 비율(9:16/1:1/16:9)·코덱(H.264/H.265) 검사 |
| `blackframes` | 시작/끝 구간 검은 화면 검사 |
| `freeze` | 멈춤(freeze) 구간 검사 — 끝까지 회복 안 되는 정지도 감지 |
| `loudness` | 음량(LUFS)·클리핑 검사 |
| `safe zone` | 플랫폼 UI 영역 자막 침범 검사 |

## Quick Start

설치:

```
pip install -e .
```

실행:

```
video-lint sample.mp4
```

JSON (CI/자동화 파이프라인용):

```
video-lint sample.mp4 --json
```

HTML (브라우저로 바로 열어보는 리포트):

```
video-lint sample.mp4 --html report.html
```

## Example Output

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: 시작 1.0초 구간이 블랙프레임으로 덮임 (0.97s); 끝 블랙프레임 없음
[WARN] loudness: 통합 음량 -35.0 LUFS (기준 -30.0 LUFS 미만 — 너무 조용함); 클리핑 미검출
[PASS] freeze: 정지 구간 없음
[SKIP] safe-zone/tiktok: 자막 파일을 안 줘서 safe zone 체크를 건너뜀 (burned-in 자막일 수 있음)
```

FAIL이 하나라도 있으면 종료 코드 `1`, 아니면 `0`.

## Project Status

**v0.1 MVP**

완료:
- CLI (사람이 보는 컬러 체크리스트 출력)
- `--json` 출력 (CI/자동화 파이프라인용)
- `--html` standalone 리포트
- ffmpeg 기반 5개 검사 (codec/resolution, blackframes, loudness, freeze, safe zone)

Roadmap:
- 실제 앱 스크린샷 기반 safe zone 검증 (`confidence: screenshot_verified`로 전환)
- 영상 미리보기(썸네일/타임라인)가 포함된 리포트
- AI 기반 수정 추천 (예: "첫 0.97초 제거 권장")

---

아래는 상세 문서입니다.

## 설치

요구사항: Python 3.11+, ffmpeg/ffprobe (시스템에 미리 설치되어 있어야 함 — macOS는 `brew install ffmpeg`).

```
git clone https://github.com/bosch2349/video-lint.git
cd video-lint
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

설치 확인:

```
video-lint --help
```

개발 중 코드를 수정하면 `-e`(editable) 설치라 재설치 없이 바로 반영됩니다. 테스트 실행은 아래 [테스트](#테스트) 절 참고.

## 상세 사용법

```
video-lint <video.mp4> [--subs subtitle.srt|.ass|.ssa] [--platform tiktok|shorts|reels|all] [--font-size PX] [--json] [--html PATH]
```

- `--subs`: `.ass`/`.ssa`는 MarginL/MarginR/MarginV, `\pos` 태그로 정확한 좌표 판정. `.srt`는 위치 정보가 없어 "하단중앙 렌더링" 가정 + 줄 수/글자 수 기반 추정치로 판정.
- `--subs` 생략 시 safe zone 체크는 SKIP (burned-in 자막 가능성 때문에 OCR 없이는 판정 불가).
- `--font-size`: SRT/ASS 기본 정렬 자막의 폰트 높이(px) 직접 지정. 생략하면 화면 높이의 약 4.5%로 추정.
- 결과 상태는 4단계: `PASS`/`WARN`/`FAIL`/`SKIP` (SKIP은 ffmpeg 미설치·실행 실패, 또는 `--subs` 미지정 등 체크 자체를 못 한 경우). 터미널(TTY)에서는 상태에 색을 입혀 보여주고, 파이프/리다이렉트 시에는 색 코드 없이 순수 텍스트로 출력됩니다.
- 종료 코드: FAIL이 하나라도 있으면 `1`, 아니면 `0`.

## Safe Zone 신뢰도

`safe_zones.json`의 목표는 "정답 좌표 제공"이 아니라 **근거와 신뢰도 관리**입니다. 플랫폼별로 `top`/`bottom`/`left`/`right` 좌표 옆에 아래 필드를 같이 기록합니다.

| 필드 | 의미 |
|---|---|
| `confidence` | `estimate`(공식 고정 spec 없음) / `conservative_estimate`(공식 수치는 있으나 광고 기준이라 organic 미확인) / `screenshot_verified`(실제 앱 스크린샷으로 실측 — 아직 어떤 플랫폼도 이 단계 아님) |
| `source` | 왜 이 신뢰도인지에 대한 설명 |
| `source_url` | 조사한 공식 문서 링크 |
| `note` | 한 줄 요약 |

조사해보니 세 플랫폼 다 "이 좌표가 100% 맞다"고 확정할 공식 고정 spec이 없었습니다:

- **TikTok** (`confidence: estimate`) — [TikTok Ads Manager 공식 문서](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads)도 고정 수치 대신 "캡션 길이/광고 포맷에 따라 safe zone이 달라진다"고만 명시. organic 영상용 공식 spec 자체가 없음.
- **YouTube Shorts** (`confidence: estimate`) — [YouTube 공식 고객센터](https://support.google.com/youtube/answer/16215842)가 명시적으로 "고정 값 없음, 편집 UI에서 동적으로 안내선 표시"라고 밝힘.
- **Instagram/Facebook Reels** (`confidence: conservative_estimate`) — [Meta 공식 Ads Help Center](https://www.facebook.com/business/help/980593475366490/)에 유일하게 구체적 수치(상단 14%/하단 35%/좌우 각 6%)가 있지만, 이건 광고(CTA/상품태그 포함) 기준이라 organic Reels UI와 같다는 보장이 없어 한 단계 낮춰서 분류. 참고용으로 `ads_safe_zone_reference_1080x1920` 필드에 Meta 수치를 따로 기록해뒀고, 실제 danger zone 판정에는 쓰지 않음.

그래서 `verified: false`는 그대로 유지했고, 앞으로 플랫폼 UI가 바뀌면 이 좌표도 같이 갱신해야 합니다. 다음 단계는 실제 앱을 켜서 스크린샷으로 UI 요소 좌표를 재고 `confidence: "screenshot_verified"`로 올리는 것 — 이건 사람이 직접 해야 하는 작업입니다.

사람이 보는 기본 출력 예:

```
$ video-lint clip.mp4 --platform tiktok
[PASS] codec/resolution: codec=h264, 1080x1920 (9:16)
[FAIL] blackframes: 시작 1.0초 구간이 블랙프레임으로 덮임 (0.97s); 끝 블랙프레임 없음
[WARN] loudness: 통합 음량 -35.0 LUFS (기준 -30.0 LUFS 미만 — 너무 조용함); 클리핑 미검출
[PASS] freeze: 정지 구간 없음
[SKIP] safe-zone/tiktok: 자막 파일을 안 줘서 safe zone 체크를 건너뜀 (burned-in 자막일 수 있음)
```

### `--json` 출력

CI/자동화 파이프라인에서 바로 파싱할 수 있는 JSON을 stdout으로 출력합니다. `safe_zones.json`/`thresholds.json`이 미검증 상태일 때 뜨는 `[WARNING]` 안내는 stdout을 오염시키지 않도록 항상 stderr로 보냅니다 — 즉 `--json` 사용 시 stdout은 항상 순수 JSON만 담습니다.

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
      "message": "시작 1.0초 구간이 블랙프레임으로 덮임 (0.97s); 끝 블랙프레임 없음",
      "details": { "window_seconds": 1.0, "start": { "covered_seconds": 0.967, "intervals": [...] }, "end": { "covered_seconds": 0, "intervals": [] } }
    }
  ]
}
```

- `overall_status`: 개별 체크 상태 중 가장 심각한 것 (`FAIL` > `WARN` > `PASS`/`SKIP`).
- `checks[].details`: 체크별 구조화된 원시 데이터(코덱/해상도, 블랙프레임 구간, LUFS/클리핑 수치, 정지 구간, safe zone 픽셀값 등). `message`를 정규식으로 긁을 필요 없이 자동화에서 바로 사용하도록 만든 필드입니다.
- `NaN`/`Infinity`(예: 완전 무음일 때 LUFS가 `-inf`) 값은 표준 JSON이 아니라서 `null`로 치환해서 내보냅니다 — 엄격한 JSON 파서에서도 안전하게 읽힙니다.
- ffprobe 자체가 실패하는 치명적 오류(파일 없음, ffmpeg 미설치 등)는 `--json`이어도 stdout에 JSON을 만들지 않고 stderr 메시지 + 종료 코드 `1`로만 알립니다. 파이프라인에서는 종료 코드를 먼저 확인하고, 0/1이면 stdout을 JSON으로 파싱하세요.

### `--html` 리포트

사람이 보기 좋은 단일 standalone HTML 파일로 결과를 저장합니다. 외부 서버/프레임워크/CDN 없이 CSS까지 파일 하나에 전부 인라인으로 들어있어서 그냥 브라우저로 열면 됩니다.

```
$ video-lint input.mp4 --html report.html
Report written:
report.html
```

- 기존 검사 로직·`CheckResult` 구조·`--json` 출력은 전혀 건드리지 않습니다 — `video_lint/report.py`가 `CheckResult` 리스트만 입력받아 HTML 문자열을 만드는 별도 레이어입니다. `--json`과 동시에 써도 됩니다(stdout은 여전히 순수 JSON, HTML은 파일로 저장).
- `Report written:` 알림은 stdout이 아니라 stderr로 나갑니다 — `--json`과 함께 써도 stdout이 오염되지 않습니다.
- 리포트 구성: 헤더(파일명/검사 시각/Overall Status) → PASS/WARN/FAIL/SKIP 개수 요약 카드 → 체크별 상태 테이블 → 체크별 `details`를 사람이 읽기 좋은 라벨(예: `covered_seconds` → `Covered Seconds`)로 펼친 상세 영역.
- 종료 코드는 `--html` 유무와 무관하게 기존과 동일 (FAIL 있으면 `1`).

### CI 활용 예 (GitHub Actions)

```yaml
- name: video-lint
  run: |
    video-lint out/final.mp4 --platform all --json > lint-result.json
    status=$(python3 -c "import json;print(json.load(open('lint-result.json'))['overall_status'])")
    echo "overall_status=$status"
    if [ "$status" = "FAIL" ]; then
      echo "::error::video-lint FAIL — lint-result.json 참고"
      exit 1
    fi
```

`jq`가 있다면 더 간단합니다:

```
video-lint out/final.mp4 --json | jq -e '.overall_status != "FAIL"'
```

## 테스트

```
for f in tests/test_*.py; do PYTHONPATH=. python3 "$f"; done
```

두 종류로 나뉩니다:

- **mock 테스트** (`test_checks.py`, `test_subtitles.py`, `test_ffmpeg_filters.py`, `test_checks_media.py`, `test_cli.py`, `test_report.py`): ffmpeg 실제 실행 없이 stderr 샘플 텍스트/함수 바꿔치기로 파싱·판정·리포트 렌더링 로직만 검증. ffmpeg 없어도 항상 통과해야 함.
- **E2E 테스트** (`test_e2e.py`): `tests/fixtures/generate.py`가 ffmpeg `lavfi` 소스로 만든 합성 영상에 CLI 전체를 실제로 돌려서 검증. ffmpeg/ffprobe가 없으면 조용히 건너뜀. fixture 상세는 [tests/fixtures/README.md](tests/fixtures/README.md) 참고.

## 라이선스

[MIT](LICENSE)
