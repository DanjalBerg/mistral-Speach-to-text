import asyncio
import logging

from . import protocol
from .audio import MicCapture, WavFileSource
from .config import Settings
from .subtitles import SubtitleBuffer
from .transcriber import RealtimeTranscriber

log = logging.getLogger("mistral_speech_to_text")


class EventHandler:
    def __init__(self, settings: Settings, buffer: SubtitleBuffer, overlay, log_file: str | None = None):
        self._buffer = buffer
        self._overlay = overlay
        self._fh = open(log_file, "a", encoding="utf-8") if log_file else None

    def __call__(self, event: dict) -> None:
        etype = event.get("type")
        if etype == protocol.TEXT_DELTA:
            self._buffer.append_delta(event.get("text", ""))
        elif etype == protocol.SEGMENT:
            self._buffer.append_segment(event.get("text", ""), event.get("speaker_id"))
        elif etype == protocol.TURN_END:
            self._buffer.close_line()
        elif etype == protocol.DONE:
            log.info("session done: %d chars", len(event.get("text", "")))
            self._write(event.get("text", ""))
        elif etype == protocol.ERROR:
            err = event.get("error", {})
            log.error("API error %s: %s", err.get("code"), err.get("message"))
        self._overlay.update(self._buffer.display_lines())

    def _write(self, text: str) -> None:
        if self._fh is not None:
            self._fh.write(text + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


async def run_app(settings: Settings, overlay) -> None:
    buffer = SubtitleBuffer(max_lines=settings.lines)
    handler = EventHandler(settings, buffer, overlay, settings.log_file)
    transcriber = RealtimeTranscriber(settings, handler)
    capture = None
    if settings.input_file:
        source = WavFileSource(settings, settings.input_file)
    else:
        capture = MicCapture(settings)
        capture.start()
        source = capture
    task = asyncio.create_task(transcriber.run())
    try:
        async for chunk in source.chunks():
            if task.done():
                break
            transcriber.feed(chunk)
        transcriber.feed_end()
        await task
    finally:
        if capture is not None:
            capture.stop()
        handler.close()
        overlay.update(buffer.display_lines())
