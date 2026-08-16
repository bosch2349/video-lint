from video_lint.checks import Status
from video_lint.subtitles import check_ass_safe_zone, check_safe_zone, check_srt_safe_zone

ASS_TEMPLATE = """[Script Info]
PlayResX: 1080
PlayResY: 1920

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,{marginv},,자막 텍스트
"""


def _zone(top=0, bottom=0, left=0, right=0, width=1080, height=1920):
    return {
        "platform": "test",
        "ref_width": width,
        "ref_height": height,
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
    }


def test_ass_marginv_overlaps_bottom_danger_zone():
    # danger zone(bottom 300px) 안쪽에 딱 붙는 MarginV -> 완전히 겹침 = FAIL
    zone = _zone(bottom=300)
    result = check_ass_safe_zone(ASS_TEMPLATE.format(marginv=50), zone, font_size_px=80)
    assert result.status == Status.FAIL


def test_ass_marginv_clears_danger_zone():
    # danger zone(bottom 300px) 위로 완전히 벗어나는 MarginV -> PASS
    zone = _zone(bottom=300)
    result = check_ass_safe_zone(ASS_TEMPLATE.format(marginv=400), zone, font_size_px=80)
    assert result.status == Status.PASS


def test_srt_short_vs_long_text_differ():
    # 짧은 한 줄은 좁은 bottom danger zone 안에 완전히 들어가 FAIL,
    # 여러 줄로 감싸지는 긴 텍스트는 danger zone 위로 걸쳐서 WARN
    zone = _zone(bottom=200)
    short = "1\n00:00:00,000 --> 00:00:02,000\n짧음\n"
    long_text = "1\n00:00:00,000 --> 00:00:02,000\n" + ("가나다라마바사아자차카타파하 " * 10) + "\n"

    short_result = check_srt_safe_zone(short, zone, font_size_px=80)
    long_result = check_srt_safe_zone(long_text, zone, font_size_px=80)

    assert "추정치" in short_result.message
    assert short_result.status != long_result.status
    assert short_result.status == Status.FAIL
    assert long_result.status == Status.WARN


def test_no_subs_returns_skip():
    result = check_safe_zone(None, "tiktok", {"reference_resolution": {}, "platforms": {}})
    assert result.status == Status.SKIP


if __name__ == "__main__":
    test_ass_marginv_overlaps_bottom_danger_zone()
    test_ass_marginv_clears_danger_zone()
    test_srt_short_vs_long_text_differ()
    test_no_subs_returns_skip()
    print("모든 테스트 통과")
