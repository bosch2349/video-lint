from video_lint.ffmpeg_filters import (
    parse_astats_output,
    parse_blackdetect_output,
    parse_ebur128_output,
    parse_freezedetect_output,
)

BLACKDETECT_SAMPLE = (
    "[blackdetect @ 0x7f0000] black_start:0 black_end:0.5 black_duration:0.5\n"
    "[blackdetect @ 0x7f0000] black_start:2.0 black_end:2.3 black_duration:0.3\n"
)

FREEZEDETECT_SAMPLE = (
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_start: 1.000000\n"
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_duration: 3.500000\n"
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_end: 4.500000\n"
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_start: 10.000000\n"
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_duration: 1.000000\n"
    "[Parsed_freezedetect_0 @ 0x7f0001] freeze_end: 11.000000\n"
)

EBUR128_SAMPLE = """[Parsed_ebur128_0 @ 0x7f0002] Summary:

  Integrated loudness:
    I:         -22.3 LUFS
    Threshold: -32.5 LUFS

  Loudness range:
    LRA:         4.1 LU

  True peak:
    Peak:       -1.2 dBFS
"""

ASTATS_SAMPLE = """[Parsed_astats_0 @ 0x7f0003] Channel: 1
[Parsed_astats_0 @ 0x7f0003] Peak level dB: -0.100000
[Parsed_astats_0 @ 0x7f0003] Peak count: 5.000000
[Parsed_astats_0 @ 0x7f0003] Overall
[Parsed_astats_0 @ 0x7f0003]     Peak level dB: -0.050000
[Parsed_astats_0 @ 0x7f0003]     Peak count: 12.000000
[Parsed_astats_0 @ 0x7f0003]     Number of samples: 44100.000000
"""


def test_parse_blackdetect_output():
    intervals = parse_blackdetect_output(BLACKDETECT_SAMPLE)
    assert intervals == [
        {"start": 0.0, "end": 0.5, "duration": 0.5},
        {"start": 2.0, "end": 2.3, "duration": 0.3},
    ]


def test_parse_blackdetect_output_empty():
    assert parse_blackdetect_output("no black frames here") == []


def test_parse_freezedetect_output():
    intervals = parse_freezedetect_output(FREEZEDETECT_SAMPLE)
    assert intervals == [
        {"start": 1.0, "duration": 3.5, "end": 4.5},
        {"start": 10.0, "duration": 1.0, "end": 11.0},
    ]


def test_parse_freezedetect_output_unresolved_at_eof():
    # 실측 확인: 영상이 끝날 때까지 정지 상태가 회복되지 않으면
    # ffmpeg가 freeze_duration/freeze_end를 아예 안 찍는다 (lavfi.freezedetect.freeze_start만 존재)
    sample = "[Parsed_freezedetect_0 @ 0x0] lavfi.freezedetect.freeze_start: 2.5\n"
    intervals = parse_freezedetect_output(sample)
    assert intervals == [{"start": 2.5, "duration": None, "end": None}]


def test_parse_ebur128_output():
    result = parse_ebur128_output(EBUR128_SAMPLE)
    assert result == {"integrated_lufs": -22.3, "true_peak_dbfs": -1.2}


def test_parse_ebur128_output_silent():
    silent = EBUR128_SAMPLE.replace("-22.3", "-inf")
    result = parse_ebur128_output(silent)
    assert result["integrated_lufs"] == float("-inf")


def test_parse_astats_output_uses_overall_block():
    result = parse_astats_output(ASTATS_SAMPLE)
    assert result["peak_level_db"] == -0.05
    assert result["peak_count"] == 12.0
    assert result["num_samples"] == 44100.0
    assert result["clipped_ratio"] == 12.0 / 44100.0


if __name__ == "__main__":
    test_parse_blackdetect_output()
    test_parse_blackdetect_output_empty()
    test_parse_freezedetect_output()
    test_parse_freezedetect_output_unresolved_at_eof()
    test_parse_ebur128_output()
    test_parse_ebur128_output_silent()
    test_parse_astats_output_uses_overall_block()
    print("모든 테스트 통과")
