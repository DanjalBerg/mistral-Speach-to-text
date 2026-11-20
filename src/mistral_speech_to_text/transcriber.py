import asyncio
import contextlib
import inspect

import websockets
from websockets.asyncio.client import connect

from . import protocol


class SessionEnded(Exception):
    def __init__(self, event: dict):
        super().__init__("received transcription.done")
        self.event = event


class SessionFailed(Exception):
    def __init__(self, event: dict):
        error = event.get("error", {})
        super().__init__(error.get("message", "error event from server"))
        self.event = event


class ProtocolError(Exception):
    pass


class RealtimeTranscriber:
    def __init__(self, settings, on_event, max_retries: int | None = None):
        self._settings = settings
        self._on_event = on_event
        self._max_retries = settings.max_retries if max_retries is None else max_retries
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._stopping = asyncio.Event()
        self._ended = False

    def feed(self, chunk: bytes) -> None:
        self._inbox.put_nowait(chunk)

    def feed_end(self) -> None:
        self._ended = True
        self._inbox.put_nowait(None)

    def stop(self) -> None:
        self._stopping.set()

    async def _emit(self, event: dict) -> None:
        result = self._on_event(event)
        if inspect.isawaitable(result):
            await result

    async def run(self) -> None:
        attempt = 0
        while True:
            try:
                await self._run_session()
                return
            except SessionEnded:
                return
            except (SessionFailed, ProtocolError):
                raise
            except (OSError, websockets.exceptions.WebSocketException):
                attempt += 1
                if self._stopping.is_set() or attempt > self._max_retries:
                    raise
                await asyncio.sleep(min(2.0 * attempt, 10.0))

    async def _run_session(self) -> None:
        headers = {}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        async with connect(
            self._settings.resolved_ws_url,
            additional_headers=headers or None,
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            first = protocol.parse_event(await ws.recv())
            await self._emit(first)
            if first.get("type") == protocol.ERROR:
                raise SessionFailed(first)
            if first.get("type") != protocol.SESSION_CREATED:
                raise ProtocolError(f"expected {protocol.SESSION_CREATED!r}, got {first.get('type')!r}")
            s = self._settings
            update = protocol.build_session_update(
                audio_format=s.audio_format,
                delay_ms=s.delay_ms,
                language=s.language,
                context_bias=s.context_bias or None,
                diarize=s.diarize or None,
                turn_detection={} if s.turn_detection else None,
            )
            await ws.send(protocol.encode(update))
            sender = asyncio.create_task(self._send_loop(ws))
            try:
                done = None
                async for raw in ws:
                    event = protocol.parse_event(raw)
                    await self._emit(event)
                    etype = event.get("type")
                    if etype == protocol.DONE:
                        done = event
                        break
                    if etype == protocol.ERROR:
                        raise SessionFailed(event)
                if done is not None:
                    raise SessionEnded(done)
                raise websockets.exceptions.ConnectionClosed(None, None)
            finally:
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await sender

    async def _send_loop(self, ws) -> None:
        while True:
            if self._stopping.is_set() or (self._ended and self._inbox.empty()):
                await ws.send(protocol.encode(protocol.build_end()))
                return
            chunk = await self._inbox.get()
            if chunk is None:
                continue
            await ws.send(protocol.encode(protocol.build_append(chunk)))
