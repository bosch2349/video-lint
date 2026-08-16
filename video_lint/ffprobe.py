import json
import subprocess


def probe_video(path: str) -> dict:
    """ffprobe로 첫 번째 비디오 스트림의 codec_name/width/height를 읽는다."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError(f"{path}에서 비디오 스트림을 찾을 수 없음")
    return streams[0]
