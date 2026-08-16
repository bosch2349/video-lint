# video-lint

> ⚠️ **safe zone / 판정 임계값 값 검증 안 됨**: `video_lint/safe_zones.json`의 TikTok/Shorts/Reels danger zone 픽셀 값은 공식 스펙 문서나 실측 스크린샷으로 확인되지 않은 추정치입니다. 실사용 전 반드시 실제 앱 스크린샷으로 UI 요소(캡션 영역/좋아요·공유 버튼/프로필/진행바 등) 좌표를 재서 재검증하세요. `video_lint/thresholds.json`의 음량(LUFS)/클리핑 하한선도 같은 이유로 미검증 참고값입니다. 두 파일 모두 `"verified": false`인 동안 CLI 실행 시마다 경고가 출력됩니다.

숏폼 영상(TikTok/Shorts/Reels) 게시 전 로컬에서 자동 QA 체크하는 CLI 도구. 서버 없음, 전부 로컬 처리.

## 설치

요구사항: Python 3.11+, ffmpeg/ffprobe (시스템에 미리 설치되어 있어야 함 — macOS는 `brew install ffmpeg`).

```
git clone <repo-url>
cd video-lint
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

설치 확인:

```
video-lint --help
```

개발 중 코드를 수정하면 `-e`(editable) 설치라 재설치 없이 바로 반영됩니다. 테스트 실행은 아래 [테스트](#테스트) 절 참고.

## 사용법

```
video-lint <video.mp4> [--subs subtitle.srt|.ass|.ssa] [--platform tiktok|shorts|reels|all] [--font-size PX] [--json]
```

- `--subs`: `.ass`/`.ssa`는 MarginL/MarginR/MarginV, `\pos` 태그로 정확한 좌표 판정. `.srt`는 위치 정보가 없어 "하단중앙 렌더링" 가정 + 줄 수/글자 수 기반 추정치로 판정.
- `--subs` 생략 시 safe zone 체크는 SKIP (burned-in 자막 가능성 때문에 OCR 없이는 판정 불가).
- `--font-size`: SRT/ASS 기본 정렬 자막의 폰트 높이(px) 직접 지정. 생략하면 화면 높이의 약 4.5%로 추정.
- 결과 상태는 4단계: `PASS`/`WARN`/`FAIL`/`SKIP` (SKIP은 ffmpeg 미설치·실행 실패, 또는 `--subs` 미지정 등 체크 자체를 못 한 경우). 터미널(TTY)에서는 상태에 색을 입혀 보여주고, 파이프/리다이렉트 시에는 색 코드 없이 순수 텍스트로 출력됩니다.
- 종료 코드: FAIL이 하나라도 있으면 `1`, 아니면 `0`.

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

- **mock 테스트** (`test_checks.py`, `test_subtitles.py`, `test_ffmpeg_filters.py`, `test_checks_media.py`, `test_cli.py`): ffmpeg 실제 실행 없이 stderr 샘플 텍스트/함수 바꿔치기로 파싱·판정 로직만 검증. ffmpeg 없어도 항상 통과해야 함.
- **E2E 테스트** (`test_e2e.py`): `tests/fixtures/generate.py`가 ffmpeg `lavfi` 소스로 만든 합성 영상에 CLI 전체를 실제로 돌려서 검증. ffmpeg/ffprobe가 없으면 조용히 건너뜀. fixture 상세는 [tests/fixtures/README.md](tests/fixtures/README.md) 참고.
