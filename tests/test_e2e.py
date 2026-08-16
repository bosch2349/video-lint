"""실제 ffmpeg로 생성한 tests/fixtures/*.mp4에 CLI 전체 파이프라인을 돌리는 E2E 스모크 테스트.
mock 테스트(test_checks_media.py 등)와 달리 진짜 ffmpeg 바이너리 출력에 의존한다.
ffmpeg/ffprobe가 없는 환경(CI 등)에서는 조용히 건너뛴다.
"""

import contextlib
import io
import json
import shutil
from pathlib import Path

from fixtures.generate import FIXTURES_DIR, generate_all

from video_lint.cli import main

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _fixture(name: str) -> str:
    path = FIXTURES_DIR / f"{name}.mp4"
    if not path.exists():
        generate_all()
    return str(path)


def _run_json(argv: list) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(argv)
    return json.loads(buf.getvalue())


def test_sample_video_start_blackframe_and_low_loudness():
    data = _run_json([_fixture("sample"), "--platform", "tiktok", "--json"])
    assert data["overall_status"] == "FAIL"
    black = next(c for c in data["checks"] if c["name"] == "blackframes")
    assert black["status"] == "FAIL"
    assert black["details"]["start"]["covered_seconds"] > 0
    loudness = next(c for c in data["checks"] if c["name"] == "loudness")
    assert loudness["status"] == "WARN"


def test_still_video_unresolved_freeze_is_fail():
    data = _run_json([_fixture("still"), "--platform", "tiktok", "--json"])
    freeze = next(c for c in data["checks"] if c["name"] == "freeze")
    assert freeze["status"] == "FAIL"
    assert freeze["details"]["unresolved"] is True


def test_still_then_motion_freeze_is_warn():
    data = _run_json([_fixture("still_then_motion"), "--platform", "tiktok", "--json"])
    freeze = next(c for c in data["checks"] if c["name"] == "freeze")
    assert freeze["status"] == "WARN"
    assert freeze["details"]["unresolved"] is False


def test_heavy_clip_flags_clipping():
    data = _run_json([_fixture("heavy_clip"), "--platform", "tiktok", "--json"])
    loudness = next(c for c in data["checks"] if c["name"] == "loudness")
    assert loudness["status"] == "WARN"
    assert "clipping" in loudness["message"]
    black = next(c for c in data["checks"] if c["name"] == "blackframes")
    assert black["status"] == "FAIL"


if __name__ == "__main__":
    if not HAS_FFMPEG:
        print("ffmpeg/ffprobe 없음 — E2E 테스트 건너뜀")
    else:
        test_sample_video_start_blackframe_and_low_loudness()
        test_still_video_unresolved_freeze_is_fail()
        test_still_then_motion_freeze_is_warn()
        test_heavy_clip_flags_clipping()
        print("모든 테스트 통과")
