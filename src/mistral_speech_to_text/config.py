import os
from dataclasses import dataclass, field

from . import protocol

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_MS = 100

_TRUE = ("1", "true", "yes", "on")


@dataclass
class Settings:
    model: str = protocol.MODEL_REALTIME
    ws_url: str | None = None
    api_key: str | None = None
    delay_ms: int = protocol.DEFAULT_DELAY_MS
    language: str | None = None
    context_bias: list[str] = field(default_factory=list)
    diarize: bool = False
    turn_detection: bool = False
    sample_rate: int = DEFAULT_SAMPLE_RATE
    chunk_ms: int = DEFAULT_CHUNK_MS
    device: str | None = None
    input_file: str | None = None
    pace_file: bool = True
    overlay: bool = True
    lines: int = 3
    font_size: int = 28
    opacity: float = 0.85
    log_file: str | None = None
    verbose: bool = False
    max_retries: int = 5

    @property
    def resolved_ws_url(self) -> str:
        if self.ws_url:
            return self.ws_url
        return protocol.default_ws_url(self.model)

    @property
    def audio_format(self) -> dict:
        return {"encoding": "pcm_s16le", "sample_rate": self.sample_rate}

    @property
    def chunk_frames(self) -> int:
        return max(1, round(self.sample_rate * self.chunk_ms / 1000))

    @property
    def chunk_bytes(self) -> int:
        return self.chunk_frames * 2

    def validate(self) -> "Settings":
        if not protocol.valid_delay_ms(self.delay_ms):
            raise ValueError(f"delay_ms must be a multiple of {protocol.STEP_MS} in [{protocol.MIN_DELAY_MS},{protocol.MAX_DELAY_MS}] or {protocol.SLOW_DELAY_MS}, got {self.delay_ms}")
        if self.diarize and self.turn_detection:
            raise ValueError("diarize and turn_detection cannot be enabled in the same session (the API rejects this combination)")
        if self.sample_rate <= 0 or self.chunk_ms <= 0:
            raise ValueError("sample_rate and chunk_ms must be positive")
        if not 0.0 < self.opacity <= 1.0:
            raise ValueError("opacity must be in (0, 1]")
        if self.lines < 1:
            raise ValueError("lines must be >= 1")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        s = cls()
        if env.get("VOXTRAL_MODEL"):
            s.model = env["VOXTRAL_MODEL"]
        if env.get("VOXTRAL_WS_URL"):
            s.ws_url = env["VOXTRAL_WS_URL"]
        s.api_key = env.get("VOXTRAL_API_KEY") or env.get("MISTRAL_API_KEY")
        if env.get("VOXTRAL_DELAY_MS"):
            s.delay_ms = int(env["VOXTRAL_DELAY_MS"])
        if env.get("VOXTRAL_LANGUAGE"):
            s.language = env["VOXTRAL_LANGUAGE"]
        if env.get("VOXTRAL_CONTEXT_BIAS"):
            s.context_bias = [x.strip() for x in env["VOXTRAL_CONTEXT_BIAS"].split(",") if x.strip()]
        if env.get("VOXTRAL_DIARIZE", "").lower() in _TRUE:
            s.diarize = True
        if env.get("VOXTRAL_TURN_DETECTION", "").lower() in _TRUE:
            s.turn_detection = True
        if env.get("VOXTRAL_DEVICE"):
            s.device = env["VOXTRAL_DEVICE"]
        if env.get("VOXTRAL_SAMPLE_RATE"):
            s.sample_rate = int(env["VOXTRAL_SAMPLE_RATE"])
        if env.get("VOXTRAL_CHUNK_MS"):
            s.chunk_ms = int(env["VOXTRAL_CHUNK_MS"])
        if env.get("VOXTRAL_LINES"):
            s.lines = int(env["VOXTRAL_LINES"])
        if env.get("VOXTRAL_FONT_SIZE"):
            s.font_size = int(env["VOXTRAL_FONT_SIZE"])
        if env.get("VOXTRAL_LOG_FILE"):
            s.log_file = env["VOXTRAL_LOG_FILE"]
        if env.get("VOXTRAL_NO_OVERLAY", "").lower() in _TRUE:
            s.overlay = False
        return s
