import asyncio
import base64

import pytest
from websockets.asyncio.server import serve

from mistral_speech_to_text import protocol
from mistral_speech_to_text.config import Settings
from mistral_speech_to_text.transcriber import RealtimeTranscriber, SessionFailed
from conftest import FakeServer, free_port


def make_settings(url, **kw):
    kw.setdefault("delay_ms", 480)
    return Settings(ws_url=url, api_key="test-key", **kw)


async def run_client(settings, events, n_chunks=5, chunk=b"\x01\x00" * 1600):
    t = RealtimeTranscriber(settings, events.append)

    async def feeder():
        for _ in range(n_chunks):
            t.feed(chunk)
        t.feed_end()

    f = asyncio.create_task(feeder())
    await t.run()
    await f


async def test_streams_audio_and_receives_events_in_order():
    async with FakeServer() as srv:
        events = []
        await run_client(make_settings(srv.url), events)

    types = [e["type"] for e in events]
    assert types[0] == protocol.SESSION_CREATED
    assert protocol.SESSION_UPDATED in types
    assert types[-1] == protocol.DONE
    deltas = [e["text"] for e in events if e["type"] == protocol.TEXT_DELTA]
    assert deltas == ["Hello", " world."]
    assert events[-1]["text"] == "Hello world."
    assert srv.received["end_seen"] is True
    assert len(srv.received["audio_chunks"]) == 5
    assert base64.b64decode(srv.received["audio_chunks"][0]) == b"\x01\x00" * 1600

    upd = srv.received["session_update"]["session"]
    assert upd["target_streaming_delay_ms"] == 480
    assert upd["audio_format"] == {"encoding": "pcm_s16le", "sample_rate": 16000}
    assert srv.received["headers"].get("authorization") == "Bearer test-key"


async def test_no_auth_header_without_api_key():
    async with FakeServer() as srv:
        settings = make_settings(srv.url)
        settings.api_key = None
        await run_client(settings, [])
    assert "authorization" not in srv.received["headers"]


async def test_session_settings_are_sent():
    async with FakeServer() as srv:
        settings = make_settings(srv.url, delay_ms=240, language="en", context_bias=["Northwind"], turn_detection=True)
        await run_client(settings, [])
    session = srv.received["session_update"]["session"]
    assert session["target_streaming_delay_ms"] == 240
    assert session["language"] == "en"
    assert session["context_bias"] == ["Northwind"]
    assert session["turn_detection"] == {}
    assert "diarize" not in session


async def test_error_event_raises_session_failed():
    async def handler(ws):
        await ws.send(protocol.encode({"type": protocol.SESSION_CREATED, "session": {}}))
        await ws.recv()
        await ws.send(protocol.encode({"type": protocol.ERROR, "error": {"code": 3051, "message": "not supported"}}))

    port = free_port()
    async with serve(handler, "127.0.0.1", port):
        settings = make_settings(f"ws://127.0.0.1:{port}/x")
        t = RealtimeTranscriber(settings, lambda e: None)
        t.feed_end()
        with pytest.raises(SessionFailed, match="not supported"):
            await t.run()


async def test_reconnects_after_connection_drop():
    async with FakeServer(drop_first=True) as srv:
        events = []
        await run_client(make_settings(srv.url), events, n_chunks=3)
    assert srv.received["connections"] == 2
    assert [e["type"] for e in events][-1] == protocol.DONE
    assert len(srv.received["audio_chunks"]) == 3
