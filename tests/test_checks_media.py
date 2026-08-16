"""blackframe/loudness/freeze 판정 로직 테스트.
실제 ffmpeg 대신 video_lint.ffmpeg_filters.run_* 함수를 mock stderr를 반환하도록 바꿔치기해서
파싱 이후의 판정(FAIL/WARN/PASS/SKIP) 분기만 검증한다.
"""

import video_lint.ffmpeg_filters as ff_module
from video_lint.checks import Status, check_blackframes, check_freeze, check_loudness, load_thresholds

THRESHOLDS = load_thresholds()

_ORIG = {
    "run_blackdetect": ff_module.run_blackdetect,
    "run_freezedetect": ff_module.run_freezedetect,
    "run_ebur128": ff_module.run_ebur128,
    "run_astats": ff_module.run_astats,
}


def _restore():
    for name, fn in _ORIG.items():
        setattr(ff_module, name, fn)


def _black_line(duration):
    return f"[blackdetect @ 0x0] black_start:0 black_end:{duration} black_duration:{duration}\n"


def test_check_blackframes_pass_when_no_black():
    ff_module.run_blackdetect = lambda path, thresholds, window: ""
    try:
        result = check_blackframes("dummy.mp4", THRESHOLDS)
        assert result.status == Status.PASS
    finally:
        _restore()


def test_check_blackframes_fail_when_window_fully_black():
    # window_seconds=1.0, fail_black_ratio=0.9 -> 0.95s면 90% 이상 커버
    ff_module.run_blackdetect = lambda path, thresholds, window: _black_line(0.95) if window == "start" else ""
    try:
        result = check_blackframes("dummy.mp4", THRESHOLDS)
        assert result.status == Status.FAIL
    finally:
        _restore()


def test_check_blackframes_warn_when_partially_black():
    ff_module.run_blackdetect = lambda path, thresholds, window: _black_line(0.2) if window == "end" else ""
    try:
        result = check_blackframes("dummy.mp4", THRESHOLDS)
        assert result.status == Status.WARN
    finally:
        _restore()


def test_check_blackframes_skip_when_ffmpeg_missing():
    def _raise(path, thresholds, window):
        raise FileNotFoundError()

    ff_module.run_blackdetect = _raise
    try:
        result = check_blackframes("dummy.mp4", THRESHOLDS)
        assert result.status == Status.SKIP
    finally:
        _restore()


def _freeze_lines(duration):
    return (
        "[Parsed_freezedetect_0 @ 0x0] freeze_start: 1.000000\n"
        f"[Parsed_freezedetect_0 @ 0x0] freeze_duration: {duration}\n"
        "[Parsed_freezedetect_0 @ 0x0] freeze_end: 2.000000\n"
    )


def test_check_freeze_pass_when_no_freeze():
    ff_module.run_freezedetect = lambda path, thresholds: ""
    try:
        assert check_freeze("dummy.mp4", THRESHOLDS).status == Status.PASS
    finally:
        _restore()


def test_check_freeze_warn_below_fail_duration():
    # fail_duration=5.0 -> 2.5s면 감지는 되지만 FAIL 기준 미만
    ff_module.run_freezedetect = lambda path, thresholds: _freeze_lines(2.5)
    try:
        assert check_freeze("dummy.mp4", THRESHOLDS).status == Status.WARN
    finally:
        _restore()


def test_check_freeze_fail_above_fail_duration():
    ff_module.run_freezedetect = lambda path, thresholds: _freeze_lines(6.0)
    try:
        assert check_freeze("dummy.mp4", THRESHOLDS).status == Status.FAIL
    finally:
        _restore()


def test_check_freeze_fail_when_unresolved_at_eof():
    # 실측으로 확인된 케이스: 영상이 끝날 때까지 정지 상태에서 회복 안 됨 -> FAIL
    ff_module.run_freezedetect = (
        lambda path, thresholds: "[Parsed_freezedetect_0 @ 0x0] lavfi.freezedetect.freeze_start: 3.0\n"
    )
    try:
        result = check_freeze("dummy.mp4", THRESHOLDS)
        assert result.status == Status.FAIL
        assert "회복되지 않음" in result.message
    finally:
        _restore()


def _ebur(integrated_lufs):
    return f"""Summary:

  Integrated loudness:
    I:         {integrated_lufs} LUFS
    Threshold: -32.5 LUFS

  True peak:
    Peak:       -1.2 dBFS
"""


def _astats(peak_db, peak_count, num_samples):
    return f"""Overall
    Peak level dB: {peak_db}
    Peak count: {peak_count}
    Number of samples: {num_samples}
"""


def test_check_loudness_pass():
    # min_integrated_lufs=-30.0, near_zero_peak_db=-0.3, max_clipped_ratio=0.0001
    ff_module.run_ebur128 = lambda path: _ebur(-20.0)
    ff_module.run_astats = lambda path: _astats(-6.0, 1, 44100)
    try:
        assert check_loudness("dummy.mp4", THRESHOLDS).status == Status.PASS
    finally:
        _restore()


def test_check_loudness_warn_too_quiet():
    ff_module.run_ebur128 = lambda path: _ebur(-35.0)
    ff_module.run_astats = lambda path: _astats(-6.0, 1, 44100)
    try:
        assert check_loudness("dummy.mp4", THRESHOLDS).status == Status.WARN
    finally:
        _restore()


def test_check_loudness_warn_clipping():
    ff_module.run_ebur128 = lambda path: _ebur(-20.0)
    ff_module.run_astats = lambda path: _astats(-0.05, 100, 44100)
    try:
        assert check_loudness("dummy.mp4", THRESHOLDS).status == Status.WARN
    finally:
        _restore()


def test_check_loudness_warn_clipping_even_with_few_peak_samples():
    # 실측 회귀 테스트: 실제로 과증폭된 sine 오디오를 AAC로 인코딩하면
    # peak count는 극히 적어도(2/220500) Peak level dB가 +21.9dB까지 튈 수 있었음
    # (디코드 후 인터샘플 피크). peak_count/num_samples 비율에 게이트를 걸면 이 경우를 놓친다 --
    # peak_level_db 자체만으로 판정해야 함.
    ff_module.run_ebur128 = lambda path: _ebur(-3.2)
    ff_module.run_astats = lambda path: _astats(21.900658, 2, 220500)
    try:
        result = check_loudness("dummy.mp4", THRESHOLDS)
        assert result.status == Status.WARN
        assert "클리핑" in result.message
    finally:
        _restore()


def test_check_loudness_skip_when_ffmpeg_missing():
    def _raise(path):
        raise FileNotFoundError()

    ff_module.run_ebur128 = _raise
    try:
        assert check_loudness("dummy.mp4", THRESHOLDS).status == Status.SKIP
    finally:
        _restore()


if __name__ == "__main__":
    test_check_blackframes_pass_when_no_black()
    test_check_blackframes_fail_when_window_fully_black()
    test_check_blackframes_warn_when_partially_black()
    test_check_blackframes_skip_when_ffmpeg_missing()
    test_check_freeze_pass_when_no_freeze()
    test_check_freeze_warn_below_fail_duration()
    test_check_freeze_fail_above_fail_duration()
    test_check_freeze_fail_when_unresolved_at_eof()
    test_check_loudness_pass()
    test_check_loudness_warn_too_quiet()
    test_check_loudness_warn_clipping()
    test_check_loudness_warn_clipping_even_with_few_peak_samples()
    test_check_loudness_skip_when_ffmpeg_missing()
    print("모든 테스트 통과")
