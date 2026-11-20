import base64

from mistral_speech_to_text import protocol


def test_valid_delay_ms_accepts_trained_values():
    for ms in (80, 160, 240, 480, 1200, 2400):
        assert protocol.valid_delay_ms(ms), ms


def test_valid_delay_ms_rejects_other_values():
    for ms in (0, 79, 100, 1280, 2000, 2401, -80):
        assert not protocol.valid_delay_ms(ms), ms


def test_default_ws_url_contains_model():
    url = protocol.default_ws_url("my-model")
    assert url.startswith("wss://api.mistral.ai/v1/audio/transcriptions/realtime?")
    assert "model=my-model" in url


def test_build_session_update_omits_unset_fields():
    msg = protocol.build_session_update(delay_ms=480, language="en")
    assert msg["type"] == protocol.SESSION_UPDATE
    assert msg["session"] == {"target_streaming_delay_ms": 480, "language": "en"}


def test_build_session_update_includes_empty_turn_detection():
    msg = protocol.build_session_update(turn_detection={})
    assert msg["session"]["turn_detection"] == {}


def test_build_append_base64_roundtrip():
    chunk = b"\x01\x02\x03\xff"
    msg = protocol.build_append(chunk)
    assert msg["type"] == protocol.INPUT_AUDIO_APPEND
    assert base64.b64decode(msg["audio"]) == chunk


def test_build_end():
    assert protocol.build_end() == {"type": protocol.INPUT_AUDIO_END}


def test_parse_event_accepts_str_and_bytes():
    raw = protocol.encode({"type": protocol.TEXT_DELTA, "text": "héllo"})
    assert protocol.parse_event(raw)["text"] == "héllo"
    assert protocol.parse_event(raw.encode("utf-8"))["type"] == protocol.TEXT_DELTA
