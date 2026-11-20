import asyncio
import wave

import numpy as np

from .config import Settings


def list_input_devices() -> list[tuple[int, str, int, float]]:
    import sounddevice as sd

    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            out.append((i, d["name"], d["max_input_channels"], d["default_samplerate"]))
    return out


def resolve_device(settings: Settings):
    import sounddevice as sd

    if settings.device is None:
        return None
    if settings.device.isdigit():
        idx = int(settings.device)
        if not sd.query_devices(idx)["max_input_channels"] > 0:
            raise SystemExit(f"device {idx} has no input channels")
        return idx
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and settings.device.lower() in d["name"].lower():
            return i
    raise SystemExit(f"no input device matching {settings.device!r}; run with --list-devices")


def resample_int16(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    data = np.asarray(data)
    if src_rate == dst_rate or len(data) == 0:
        return data.astype(np.int16, copy=False)
    duration = len(data) / src_rate
    n_dst = max(1, int(round(duration * dst_rate)))
    src_pos = np.linspace(0.0, duration, num=len(data), endpoint=False)
    dst_pos = np.linspace(0.0, duration, num=n_dst, endpoint=False)
    return np.interp(dst_pos, src_pos, data).astype(np.int16)


class MicCapture:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._inbox: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None
        self._src_rate = settings.sample_rate

    def _callback(self, indata, frames, time_info, status):
        if self._inbox is None or self._loop is None:
            return
        data = indata[:, 0] if getattr(indata, "ndim", 1) > 1 else indata
        pcm = resample_int16(data, self._src_rate, self._settings.sample_rate)
        self._loop.call_soon_threadsafe(self._inbox.put_nowait, pcm.tobytes())

    def start(self) -> None:
        import sounddevice as sd

        self._inbox = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        device = resolve_device(self._settings)
        blocksize = max(1, round(self._settings.sample_rate * self._settings.chunk_ms / 1000))
        try:
            self._stream = sd.InputStream(
                device=device, channels=1, dtype="int16",
                samplerate=self._settings.sample_rate, blocksize=blocksize,
                callback=self._callback,
            )
            self._src_rate = self._settings.sample_rate
        except sd.PortAudioError:
            if device is None:
                self._src_rate = int(sd.default.samplerate)
            else:
                self._src_rate = int(sd.query_devices(device)["default_samplerate"])
            blocksize = max(1, round(self._src_rate * self._settings.chunk_ms / 1000))
            self._stream = sd.InputStream(
                device=device, channels=1, dtype="int16",
                samplerate=self._src_rate, blocksize=blocksize,
                callback=self._callback,
            )
        self._stream.start()

    async def chunks(self):
        if self._inbox is None:
            raise RuntimeError("call start() before chunks()")
        while True:
            yield await self._inbox.get()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class WavFileSource:
    def __init__(self, settings: Settings, path: str):
        self._settings = settings
        self._path = path

    async def chunks(self):
        with wave.open(self._path, "rb") as wav:
            if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                raise SystemExit("only 16-bit mono WAV files are supported")
            src_rate = wav.getframerate()
            frames_per_chunk = max(1, round(src_rate * self._settings.chunk_ms / 1000))
            pace = self._settings.chunk_ms / 1000.0 if self._settings.pace_file else 0.0
            while True:
                raw = wav.readframes(frames_per_chunk)
                if not raw:
                    return
                pcm = resample_int16(np.frombuffer(raw, dtype=np.int16), src_rate, self._settings.sample_rate)
                yield pcm.tobytes()
                if pace:
                    await asyncio.sleep(pace)
