import pytest

from mistral_speech_to_text import protocol
from mistral_speech_to_text.config import Settings


def test_resolved_ws_url_defaults_to_mistral_realtime_endpoint():
    s = Settings()
    assert s.resolved_ws_url == protocol.default_ws_url(protocol.MODEL_REALTIME)
    assert "voxtral-mini-transcribe-realtime-3" in s.resolved_ws_url


def test_resolved_ws_url_prefers_explicit_url():
    s = Settings(ws_url="ws://127.0.0.1:8000/v1/realtime")
    assert s.resolved_ws_url == "ws://127.0.0.1:8000/v1/realtime"


def test_audio_format_and_chunk_bytes():
    s = Settings(sample_rate=16000, chunk_ms=100)
    assert s.audio_format == {"encoding": "pcm_s16le", "sample_rate": 16000}
    assert s.chunk_frames == 1600
    assert s.chunk_bytes == 3200


def test_from_env(monkeypatch):
    monkeypatch.setenv("VOXTRAL_MODEL", "custom-model")
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-test")
    monkeypatch.setenv("VOXTRAL_DELAY_MS", "240")
    monkeypatch.setenv("VOXTRAL_LANGUAGE", "fr")
    monkeypatch.setenv("VOXTRAL_CONTEXT_BIAS", "Northwind, Quillara ,")
    monkeypatch.setenv("VOXTRAL_DIARIZE", "true")
    monkeypatch.setenv("VOXTRAL_NO_OVERLAY", "1")
    monkeypatch.setenv("VOXTRAL_LINES", "5")
    s = Settings.from_env()
    assert s.model == "custom-model"
    assert s.api_key == "sk-test"
    assert s.delay_ms == 240
    assert s.language == "fr"
    assert s.context_bias == ["Northwind", "Quillara"]
    assert s.diarize is True
    assert s.overlay is False
    assert s.lines == 5


def test_from_env_voxtral_api_key_wins(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-mistral")
    monkeypatch.setenv("VOXTRAL_API_KEY", "sk-voxtral")
    assert Settings.from_env().api_key == "sk-voxtral"


def test_validate_rejects_bad_delay():
    with pytest.raises(ValueError, match="delay_ms"):
        Settings(delay_ms=100).validate()


def test_validate_rejects_diarize_with_turn_detection():
    with pytest.raises(ValueError, match="diarize and turn_detection"):
        Settings(diarize=True, turn_detection=True).validate()


def test_validate_accepts_edge_delays():
    Settings(delay_ms=80).validate()
    Settings(delay_ms=1200).validate()
    Settings(delay_ms=2400).validate()
