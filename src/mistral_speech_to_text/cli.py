import argparse
import argparse
import asyncio
import logging
import os
import sys
import threading

from . import protocol
from .app import run_app
from .config import Settings
from .overlay import ConsoleOverlay


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mistral-stt",
        description="Realtime transparent subtitle overlay using Voxtral Mini Transcribe Realtime 3 "
                    "(Mistral API WebSocket, or a self-hosted vLLM /v1/realtime endpoint).",
    )
    p.add_argument("--model", help=f"model name (default {protocol.MODEL_REALTIME})")
    p.add_argument("--url", dest="ws_url", help="realtime WebSocket URL; default is built from --model as wss://api.mistral.ai/v1/audio/transcriptions/realtime?model=...")
    p.add_argument("--api-key", help="API key for the Mistral API (default: $VOXTRAL_API_KEY or $MISTRAL_API_KEY); omit for self-hosted")
    p.add_argument("--delay-ms", type=int, help=f"target_streaming_delay_ms: multiple of {protocol.STEP_MS} in [{protocol.MIN_DELAY_MS},{protocol.MAX_DELAY_MS}] or {protocol.SLOW_DELAY_MS} (default {protocol.DEFAULT_DELAY_MS})")
    p.add_argument("--language", help="ISO 639-1 code, e.g. en; omit for auto-detect")
    p.add_argument("--context-bias", action="append", help="keyphrase to bias recognition; repeatable")
    p.add_argument("--diarize", action="store_true", help="label speakers (transcription.segment events)")
    p.add_argument("--turn-detection", action="store_true", help="emit turn.* events and close caption lines at turn.end (incompatible with --diarize)")
    p.add_argument("--device", help="input device index or name substring (default: system default mic)")
    p.add_argument("--list-devices", action="store_true", help="list input audio devices and exit")
    p.add_argument("--input-file", help="stream a 16-bit mono WAV file instead of the microphone")
    p.add_argument("--no-pace", action="store_true", help="with --input-file, send audio as fast as possible instead of realtime pace")
    p.add_argument("--sample-rate", type=int, help=f"capture/stream sample rate (default {Settings.sample_rate})")
    p.add_argument("--chunk-ms", type=int, help=f"audio chunk size in ms (default {Settings.chunk_ms})")
    p.add_argument("--no-overlay", action="store_true", help="print subtitles to the console instead of showing the transparent overlay")
    p.add_argument("--lines", type=int, help="max caption lines shown in the overlay (default 3)")
    p.add_argument("--font-size", type=int, help="overlay font size in px (default 28)")
    p.add_argument("--log-file", help="append the final transcript of each session to this file")
    p.add_argument("--max-retries", type=int, help="WebSocket reconnect attempts (default 5)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p


def settings_from_args(args) -> Settings:
    s = Settings.from_env()
    for name in ("model", "ws_url", "api_key", "delay_ms", "language", "device", "input_file", "sample_rate", "chunk_ms", "lines", "font_size", "log_file", "max_retries"):
        value = getattr(args, name)
        if value is not None:
            setattr(s, name, value)
    if args.context_bias:
        s.context_bias = list(args.context_bias)
    if args.diarize:
        s.diarize = True
    if args.turn_detection:
        s.turn_detection = True
    if args.no_pace:
        s.pace_file = False
    if args.no_overlay:
        s.overlay = False
    if args.verbose:
        s.verbose = True
    return s.validate()


def qt_overlay_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except Exception:
        return False
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.environ.get("QT_QPA_PLATFORM")
    ):
        return False
    return True


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.list_devices:
        from .audio import list_input_devices

        for idx, name, channels, rate in list_input_devices():
            print(f"{idx}: {name} (inputs={channels}, default_rate={rate})")
        return 0

    try:
        settings = settings_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    log = logging.getLogger("mistral_speech_to_text")
    if settings.overlay and qt_overlay_available():
        from .overlay import QtOverlay

        overlay = QtOverlay(settings)
        worker = threading.Thread(target=lambda: asyncio.run(run_app(settings, overlay)), daemon=True)
        worker.start()
        try:
            overlay.run()
        except KeyboardInterrupt:
            pass
        finally:
            overlay.close()
    else:
        if settings.overlay:
            log.warning("Qt overlay not available here; falling back to console output (Linux terminal). Use --no-overlay to silence this warning.")
        try:
            asyncio.run(run_app(settings, ConsoleOverlay(settings)))
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
