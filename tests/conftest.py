import socket

from websockets.asyncio.server import serve

from mistral_speech_to_text import protocol


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_handler(deltas, final, received, drop_first=False):
    async def handler(ws):
        received["headers"] = dict(ws.request.headers)
        received["connections"] = received.get("connections", 0) + 1
        await ws.send(protocol.encode({
            "type": protocol.SESSION_CREATED,
            "session": {"model": "fake", "audio_format": {"encoding": "pcm_s16le", "sample_rate": 16000}},
        }))
        if drop_first and received["connections"] == 1:
            await ws.close()
            return
        msg = protocol.parse_event(await ws.recv())
        received["session_update"] = msg
        if msg["type"] != protocol.SESSION_UPDATE:
            await ws.send(protocol.encode({"type": protocol.ERROR, "error": {"code": 1, "message": "expected session.update"}}))
            return
        await ws.send(protocol.encode({"type": protocol.SESSION_UPDATED, "session": msg["session"]}))
        sent_deltas = False
        async for raw in ws:
            event = protocol.parse_event(raw)
            if event["type"] == protocol.INPUT_AUDIO_APPEND:
                received.setdefault("audio_chunks", []).append(event["audio"])
                if not sent_deltas:
                    sent_deltas = True
                    for text in deltas:
                        await ws.send(protocol.encode({"type": protocol.TEXT_DELTA, "text": text}))
            elif event["type"] == protocol.INPUT_AUDIO_END:
                received["end_seen"] = True
                await ws.send(protocol.encode({"type": protocol.DONE, "text": final}))
                return
    return handler


class FakeServer:
    def __init__(self, deltas=("Hello", " world."), final="Hello world.", drop_first=False):
        self.deltas = deltas
        self.final = final
        self.drop_first = drop_first
        self.received = {}
        self.url = None
        self._server = None

    async def __aenter__(self):
        port = free_port()
        self._server = await serve(
            make_handler(self.deltas, self.final, self.received, self.drop_first),
            "127.0.0.1", port,
        )
        self.url = f"ws://127.0.0.1:{port}/v1/audio/transcriptions/realtime?model=fake"
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()
        return False
