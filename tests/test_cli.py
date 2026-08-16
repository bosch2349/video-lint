import json

from video_lint.checks import CheckResult, Status
from video_lint.cli import _json_safe, _to_json, build_parser


def test_json_safe_converts_inf_and_nan_to_null():
    assert _json_safe(float("-inf")) is None
    assert _json_safe(float("inf")) is None
    assert _json_safe(float("nan")) is None
    assert _json_safe(3.14) == 3.14


def test_json_safe_recurses_into_dict_and_list():
    value = {"a": float("-inf"), "b": [1, float("nan"), {"c": float("inf")}]}
    assert _json_safe(value) == {"a": None, "b": [1, None, {"c": None}]}


def test_to_json_produces_valid_parseable_json_with_expected_shape():
    results = [
        CheckResult("codec/resolution", Status.PASS, "ok", {"codec": "h264"}),
        CheckResult("loudness", Status.WARN, "too quiet", {"integrated_lufs": float("-inf")}),
    ]
    raw = _to_json("video.mp4", results, Status.WARN)
    data = json.loads(raw)  # 유효한 JSON이 아니면 여기서 예외 발생

    assert data["file"] == "video.mp4"
    assert data["overall_status"] == "WARN"
    assert len(data["checks"]) == 2
    assert data["checks"][0] == {
        "name": "codec/resolution",
        "status": "PASS",
        "message": "ok",
        "details": {"codec": "h264"},
    }
    assert data["checks"][1]["details"]["integrated_lufs"] is None


def test_json_flag_defaults_to_false_and_can_be_enabled():
    parser = build_parser()
    assert parser.parse_args(["video.mp4"]).json is False
    assert parser.parse_args(["video.mp4", "--json"]).json is True


def test_html_flag_defaults_to_none_and_accepts_a_path():
    parser = build_parser()
    assert parser.parse_args(["video.mp4"]).html is None
    assert parser.parse_args(["video.mp4", "--html", "report.html"]).html == "report.html"


if __name__ == "__main__":
    test_json_safe_converts_inf_and_nan_to_null()
    test_json_safe_recurses_into_dict_and_list()
    test_to_json_produces_valid_parseable_json_with_expected_shape()
    test_json_flag_defaults_to_false_and_can_be_enabled()
    test_html_flag_defaults_to_none_and_accepts_a_path()
    print("모든 테스트 통과")
