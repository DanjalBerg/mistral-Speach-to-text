import base64
import json
from urllib.parse import urlencode

MODEL_REALTIME = "voxtral-mini-transcribe-realtime-3"
MODEL_BATCH = "voxtral-mini-transcribe-3"
DEFAULT_API_BASE = "wss://api.mistral.ai"
REALTIME_PATH = "/v1/audio/transcriptions/realtime"

SESSION_CREATED = "session.created"
SESSION_UPDATED = "session.updated"
SESSION_UPDATE = "session.update"
INPUT_AUDIO_APPEND = "input_audio.append"
INPUT_AUDIO_END = "input_audio.end"
TEXT_DELTA = "transcription.text.delta"
SEGMENT = "transcription.segment"
DONE = "transcription.done"
ERROR = "error"
TURN_PREFIX = "turn."
TURN_END = "turn.end"

MIN_DELAY_MS = 80
MAX_DELAY_MS = 1200
STEP_MS = 80
SLOW_DELAY_MS = 2400
DEFAULT_DELAY_MS = 480


def valid_delay_ms(ms: int) -> bool:
    if ms == SLOW_DELAY_MS:
        return True
    return MIN_DELAY_MS <= ms <= MAX_DELAY_MS and ms % STEP_MS == 0


def default_ws_url(model: str = MODEL_REALTIME, base: str = DEFAULT_API_BASE) -> str:
    return f"{base}{REALTIME_PATH}?{urlencode({'model': model})}"


def build_session_update(audio_format=None, delay_ms=None, language=None, context_bias=None, diarize=None, turn_detection=None) -> dict:
    session = {}
    if audio_format is not None:
        session["audio_format"] = audio_format
    if delay_ms is not None:
        session["target_streaming_delay_ms"] = delay_ms
    if language is not None:
        session["language"] = language
    if context_bias:
        session["context_bias"] = list(context_bias)
    if diarize is not None:
        session["diarize"] = diarize
    if turn_detection is not None:
        session["turn_detection"] = turn_detection
    return {"type": SESSION_UPDATE, "session": session}


def build_append(chunk: bytes) -> dict:
    return {"type": INPUT_AUDIO_APPEND, "audio": base64.b64encode(chunk).decode("ascii")}


def build_end() -> dict:
    return {"type": INPUT_AUDIO_END}


def encode(message: dict) -> str:
    return json.dumps(message, separators=(",", ":"))


def parse_event(raw) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)
