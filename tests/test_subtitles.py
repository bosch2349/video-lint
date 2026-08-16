from video_lint.checks import Status
from video_lint.subtitles import check_ass_safe_zone, check_safe_zone, check_srt_safe_zone, load_safe_zones

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

    assert "Estimate" in short_result.message
    assert short_result.status != long_result.status
    assert short_result.status == Status.FAIL
    assert long_result.status == Status.WARN


def test_no_subs_returns_skip():
    result = check_safe_zone(None, "tiktok", {"reference_resolution": {}, "platforms": {}})
    assert result.status == Status.SKIP


def test_bundled_safe_zones_json_has_source_and_confidence_metadata():
    zones = load_safe_zones()
    assert zones["verified"] is False  # 조사만으로 확정 불가 -> verified=true로 바꾸지 않음

    platforms = zones["platforms"]
    assert platforms["tiktok"]["confidence"] == "estimate"
    assert platforms["shorts"]["confidence"] == "estimate"
    assert platforms["reels"]["confidence"] == "conservative_estimate"

    for platform in ("tiktok", "shorts", "reels"):
        entry = platforms[platform]
        assert entry["source"]
        assert entry["source_url"].startswith("https://")
        assert entry["note"]
        # 신규 메타데이터 필드가 기존 danger zone 판정용 키는 건드리지 않음
        for key in ("top", "bottom", "left", "right"):
            assert isinstance(entry[key], (int, float))


def test_bundled_safe_zones_json_still_drives_real_danger_zone_check():
    # source/confidence/note 등 신규 필드가 섞여 들어가도 기존 판정 로직이 깨지지 않는지 확인
    zones = load_safe_zones()
    tiktok_zone = zones["platforms"]["tiktok"]
    zone = {
        "platform": "tiktok",
        "ref_width": zones["reference_resolution"]["width"],
        "ref_height": zones["reference_resolution"]["height"],
        **tiktok_zone,
    }
    # bottom danger zone 안쪽에 딱 붙는 MarginV -> FAIL이 그대로 나와야 함
    content = ASS_TEMPLATE.format(marginv=10)
    result = check_ass_safe_zone(content, zone, font_size_px=80)
    assert result.status == Status.FAIL


if __name__ == "__main__":
    test_ass_marginv_overlaps_bottom_danger_zone()
    test_ass_marginv_clears_danger_zone()
    test_srt_short_vs_long_text_differ()
    test_no_subs_returns_skip()
    test_bundled_safe_zones_json_has_source_and_confidence_metadata()
    test_bundled_safe_zones_json_still_drives_real_danger_zone_check()
    print("모든 테스트 통과")
