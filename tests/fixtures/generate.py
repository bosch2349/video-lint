"""video-lint E2E 테스트용 합성 영상 fixture 생성기.

외부 파일 다운로드 없이 ffmpeg의 lavfi 소스(color/testsrc/sine/anullsrc)만으로 만든다.
생성된 .mp4는 git에 커밋하지 않고(용량/바이너리 diff 회피) 매번 이 스크립트로 재생성한다.

재생성: python3 tests/fixtures/generate.py
"""

import subprocess
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def _run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def generate_sample(out_dir: Path = FIXTURES_DIR) -> Path:
    """1080x1920, 5초: 검은화면 1초 + testsrc 4초, 무음 오디오.
    -> codec/resolution PASS, blackframes(시작) FAIL, loudness(너무 조용함) WARN."""
    path = out_dir / "sample.mp4"
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=30",
            "-f", "lavfi", "-i", "testsrc=s=1080x1920:d=4:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=5",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-map", "2:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(path),
        ]
    )
    return path


def generate_still(out_dir: Path = FIXTURES_DIR) -> Path:
    """1080x1920, 3초 내내 완전 정지(끝까지 회복 안 됨).
    -> freeze FAIL (미종결 정지 구간)."""
    path = out_dir / "still.mp4"
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=3:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )
    return path


def generate_still_then_motion(out_dir: Path = FIXTURES_DIR) -> Path:
    """640x360, 정지 2.5초 후 움직임으로 회복.
    -> freeze WARN (정지 구간은 있지만 fail_duration 미만)."""
    path = out_dir / "still_then_motion.mp4"
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=2.5:r=30",
            "-f", "lavfi", "-i", "testsrc=s=640x360:d=2:r=30",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )
    return path


def generate_heavy_clip(out_dir: Path = FIXTURES_DIR) -> Path:
    """1080x1920: 검은화면 시작/끝 1초 + 과증폭된 사인파 오디오(실제 클리핑).
    -> blackframes FAIL(시작+끝), loudness 클리핑 WARN."""
    path = out_dir / "heavy_clip.mp4"
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=30",
            "-f", "lavfi", "-i", "testsrc=s=1080x1920:d=3:r=30",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100:duration=5",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a]volume=40dB[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(path),
        ]
    )
    return path


def generate_all(out_dir: Path = FIXTURES_DIR) -> dict:
    return {
        "sample": generate_sample(out_dir),
        "still": generate_still(out_dir),
        "still_then_motion": generate_still_then_motion(out_dir),
        "heavy_clip": generate_heavy_clip(out_dir),
    }


if __name__ == "__main__":
    for fixture_name, fixture_path in generate_all().items():
        print(f"{fixture_name}: {fixture_path}")
