import tempfile
from pathlib import Path

from video_lint.checks import CheckResult, Status
from video_lint.report import generate_html_report, write_html_report


def _results():
    return [
        CheckResult(
            "codec/resolution",
            Status.PASS,
            "codec=h264, 1080x1920 (9:16)",
            {"codec": "h264", "width": 1080, "height": 1920},
        ),
        CheckResult(
            "blackframes",
            Status.FAIL,
            "시작 1.0초 구간이 블랙프레임으로 덮임 (0.97s)",
            {
                "window_seconds": 1.0,
                "start": {
                    "covered_seconds": 0.967,
                    "intervals": [{"start": 0.0, "end": 0.967, "duration": 0.967}],
                },
                "end": {"covered_seconds": 0, "intervals": []},
            },
        ),
        CheckResult("loudness", Status.WARN, "통합 음량 -35.0 LUFS", {"integrated_lufs": -35.0}),
        CheckResult("safe-zone/tiktok", Status.SKIP, "자막 파일을 안 줘서 건너뜀", {"platform": "tiktok"}),
    ]


def test_report_contains_key_sections_and_filename():
    out = generate_html_report("test.mp4", _results(), Status.FAIL)
    assert "<!doctype html>" in out.lower()
    assert "video-lint" in out
    assert "test.mp4" in out
    assert "codec/resolution" in out
    assert "blackframes" in out
    assert "loudness" in out
    assert "safe-zone/tiktok" in out


def test_report_shows_every_status_badge():
    out = generate_html_report("test.mp4", _results(), Status.FAIL)
    assert ">PASS<" in out
    assert ">WARN<" in out
    assert ">FAIL<" in out
    assert ">SKIP<" in out


def test_report_renders_nested_details_as_readable_labels():
    out = generate_html_report("test.mp4", _results(), Status.FAIL)
    # covered_seconds 같은 raw 키 대신 사람이 읽는 라벨로 변환
    assert "Covered Seconds" in out
    assert "0.967" in out
    assert "Window Seconds" in out


def test_report_escapes_html_in_message_and_details():
    results = [CheckResult("x", Status.WARN, "<script>alert(1)</script>", {"note": "<b>bad</b>"})]
    out = generate_html_report("test.mp4", results, Status.WARN)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
    assert "<b>bad</b>" not in out


def test_report_is_standalone_with_no_external_references():
    out = generate_html_report("test.mp4", _results(), Status.FAIL)
    assert "<link " not in out
    assert "http://" not in out
    assert "https://" not in out
    assert "<style>" in out  # CSS가 인라인으로 포함됨


def test_write_html_report_creates_file_on_disk():
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "report.html"
        written = write_html_report("test.mp4", _results(), Status.FAIL, str(out_path))
        assert written == out_path
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "video-lint" in content


if __name__ == "__main__":
    test_report_contains_key_sections_and_filename()
    test_report_shows_every_status_badge()
    test_report_renders_nested_details_as_readable_labels()
    test_report_escapes_html_in_message_and_details()
    test_report_is_standalone_with_no_external_references()
    test_write_html_report_creates_file_on_disk()
    print("모든 테스트 통과")
