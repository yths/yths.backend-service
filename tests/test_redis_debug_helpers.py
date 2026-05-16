import time

import redis_debug


# ---------- _stream_age ----------

def test_stream_age_returns_question_mark_on_garbage():
    assert redis_debug._stream_age("not an eid") == "?"
    assert redis_debug._stream_age(None) == "?"


def test_stream_age_picks_right_unit():
    now_ms = int(time.time() * 1000)

    def age(offset_ms):
        return redis_debug._stream_age(f"{now_ms - offset_ms}-0")

    assert age(500).endswith("ms")
    out_5s = age(5_000)
    assert out_5s.endswith("s") and not out_5s.endswith("ms")
    assert age(120_000).endswith("m")
    assert age(7_200_000).endswith("h")
    assert age(172_800_000).endswith("d")


def test_stream_age_clamps_future_timestamps_to_zero():
    future_ms = int(time.time() * 1000) + 60_000
    out = redis_debug._stream_age(f"{future_ms}-0")
    # Negative ages clamp to 0; result must still be a valid short string.
    assert out.endswith("ms")
    assert int(out[:-2]) == 0


# ---------- _truncate ----------

def test_truncate_short_string_passes_through():
    assert redis_debug._truncate("hello") == "hello"


def test_truncate_replaces_newlines_with_spaces():
    assert redis_debug._truncate("hello\nworld") == "hello world"


def test_truncate_cuts_overlong_strings_with_ellipsis():
    out = redis_debug._truncate("x" * 200, limit=10)
    assert len(out) == 10
    assert out.endswith("…")


# ---------- _format_measurement ----------

def test_format_measurement_renders_json_dict_as_kv_pairs():
    out = redis_debug._format_measurement({b"measurement": b'{"a": 1, "b": "two"}'})
    assert "a=1" in out and "b=two" in out


def test_format_measurement_renders_empty_dict_as_braces():
    assert redis_debug._format_measurement({b"measurement": b"{}"}) == "{}"


def test_format_measurement_falls_back_on_non_json_measurement():
    out = redis_debug._format_measurement({b"measurement": b"not json"})
    assert "not json" in out


def test_format_measurement_without_measurement_field_renders_all_fields():
    out = redis_debug._format_measurement({b"x": b"1", b"y": b"2"})
    assert "x=1" in out and "y=2" in out


def test_format_measurement_with_empty_payload_returns_marker():
    assert redis_debug._format_measurement({}) == "[no fields]"


# ---------- _decode ----------

def test_decode_bytes_returns_utf8_string():
    assert redis_debug._decode(b"hello") == "hello"


def test_decode_non_utf8_bytes_returns_repr():
    out = redis_debug._decode(b"\xff\xfe")
    assert out.startswith("b'") or "\\xff" in out


def test_decode_non_bytes_passes_through_str():
    assert redis_debug._decode(42) == "42"
