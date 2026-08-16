from video_lint.checks import Status, check_codec_resolution


def test_pass_9_16_h264():
    result = check_codec_resolution({"codec_name": "h264", "width": 1080, "height": 1920})
    assert result.status == Status.PASS


def test_warn_bad_ratio():
    result = check_codec_resolution({"codec_name": "h264", "width": 1280, "height": 960})
    assert result.status == Status.WARN
    assert "비율" in result.message


def test_warn_bad_codec():
    result = check_codec_resolution({"codec_name": "vp9", "width": 1080, "height": 1920})
    assert result.status == Status.WARN
    assert "코덱" in result.message


def test_fail_missing_dimensions():
    result = check_codec_resolution({"codec_name": "h264"})
    assert result.status == Status.FAIL


if __name__ == "__main__":
    test_pass_9_16_h264()
    test_warn_bad_ratio()
    test_warn_bad_codec()
    test_fail_missing_dimensions()
    print("모든 테스트 통과")
