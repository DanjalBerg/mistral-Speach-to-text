import wave

import numpy as np

from mistral_speech_to_text.app import run_app
from mistral_speech_to_text.audio import resample_int16
from mistral_speech_to_text.config import Settings
from conftest import FakeServer


class StubOverlay:
    def __init__(self):
        self.updates = []

    def update(self, lines):
        self.updates.append(list(lines))


def write_wav(path, seconds=0.5, rate=16000):
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    data = (0.3 * 32767 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())


def test_resample_identity():
    data = np.arange(100, dtype=np.int16)
    out = resample_int16(data, 16000, 16000)
    assert np.array_equal(out, data)


def test_resample_downsample_length():
    data = np.zeros(4800, dtype=np.int16)
    out = resample_int16(data, 48000, 16000)
    assert out.dtype == np.int16
    assert abs(len(out) - 1600) <= 1


async def test_run_app_with_wav_file_and_fake_server(tmp_path):
    wav = tmp_path / "tone.wav"
    write_wav(wav)
    async with FakeServer(deltas=("Hi", " there."), final="Hi there.") as srv:
        settings = Settings(ws_url=srv.url, input_file=str(wav), pace_file=False, chunk_ms=100, overlay=False)
        overlay = StubOverlay()
        await run_app(settings, overlay)
    assert overlay.updates[-1] == ["Hi there."]
    assert srv.received["end_seen"] is True
    assert len(srv.received["audio_chunks"]) >= 4
