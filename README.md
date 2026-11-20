# mistral-Speach-to-text

Realtime **speech-to-text live subtitles**: a transparent, always-on-top, click-through foreground
overlay that captions whatever is being said (microphone, system audio, or a file) on top of any
other app — meetings, videos, calls, games. Powered by the **Mistral API** and
**Voxtral Mini Transcribe Realtime 3** (`voxtral-mini-transcribe-realtime-3`), which streams
transcripts over a WebSocket at sub-second latency.

> Naming note: the Voxtral "Transcribe" family is **speech → text** — exactly what live subtitles
> need. The realtime variant streams over WebSocket; the batch `voxtral-mini-transcribe-3`
> (`/v1/audio/transcriptions`) is for recorded files. (Mistral's text → speech model is the separate
> Voxtral TTS 3 family.)

## How it works

```
microphone / loopback / WAV file
        │  16 kHz mono PCM s16le, 100 ms chunks
        ▼
RealtimeTranscriber ──WebSocket──▶ wss://api.mistral.ai/v1/audio/transcriptions/realtime?model=voxtral-mini-transcribe-realtime-3
        │  session.update / input_audio.append / input_audio.end   (Authorization: Bearer $MISTRAL_API_KEY)
        ▼  transcription.text.delta (append-only), transcription.segment, turn.*
SubtitleBuffer ──▶ cross-platform Qt overlay (bottom-center pill) or console fallback + log file
```

Protocol per the [Mistral realtime transcription docs](https://docs.mistral.ai/studio/audio/speech-to-text/transcribe-in-realtime):
`session.created` → send `session.update` → `session.updated` → stream `input_audio.append` → receive
`transcription.text.delta` → send `input_audio.end` → `transcription.done`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all,test]"     # websockets + numpy + sounddevice (mic) + PySide6 (Qt overlay)
```

- `pip install -e .` — core only (WebSocket client + console mode)
- `[audio]` — microphone capture (`sounddevice`)
- `[overlay]` — transparent Qt window (`PySide6`)
- `[test]` — pytest suite

## Run

```bash
export MISTRAL_API_KEY=...        # https://console.mistral.ai/api-keys
mistral-stt                                   # mic → transparent overlay
mistral-stt --no-overlay                      # mic → console captions (Linux terminal fallback)
mistral-stt --turn-detection                  # close the caption line at each turn.end
mistral-stt --diarize                         # prefix caption lines with speaker labels
mistral-stt --delay-ms 240 --language en      # faster captions; pin the language
mistral-stt --context-bias Northwind --context-bias Quillara
mistral-stt --list-devices                    # list microphones
mistral-stt --device "USB"                    # pick a microphone by index or name
mistral-stt --input-file chat.wav             # stream a 16-bit mono WAV instead of the mic
mistral-stt --log-file transcript.txt         # save the final transcript of each session
```

### Overlay behavior (cross-platform Qt, Linux fallback)

The overlay is a frameless, translucent, always-on-top, click-through window pinned bottom-center
(Windows: `WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE` via `SetWindowLongW`; macOS/Linux:
`WA_TranslucentBackground` + `WindowStaysOnTopHint`). If PySide6 is missing or there is no display
(e.g. headless Linux / SSH), the app automatically **falls back to console output** — the same
captions in the terminal. `--no-overlay` forces console mode. On Linux X11 the translucent pill needs
a compositing window manager; on Wayland or without one, use `--no-overlay`.

### Audio sources

- **Microphone**: default; `--device` selects by index or name substring (`--list-devices`).
  Captured as 16 kHz mono `pcm_s16le`; devices that can't run at 16 kHz are resampled.
- **System audio / loopback**: select a loopback device (Windows: "Stereo Mix", a WASAPI loopback
  device, or a virtual cable like VB-Cable → `--device "Stereo Mix"`; macOS: a virtual device such
  as BlackHole).
- **File**: `--input-file x.wav` streams a 16-bit mono WAV at realtime pace (`--no-pace` for max speed).

### Self-hosted vLLM (optional)

`--url ws://gpu-box:8000/v1/realtime` points the app at a self-hosted
`vllm serve mistralai/Voxtral-Mini-4B-Realtime-2602` server (≥16 GB GPU, exposes WebSocket
`/v1/realtime`); no API key needed in that case.

## Configuration

Every flag has an env-var equivalent (see `.env.example`): `MISTRAL_API_KEY` / `VOXTRAL_API_KEY`,
`VOXTRAL_MODEL`, `VOXTRAL_WS_URL`, `VOXTRAL_DELAY_MS`, `VOXTRAL_LANGUAGE`, `VOXTRAL_CONTEXT_BIAS`
(comma-separated), `VOXTRAL_DIARIZE`, `VOXTRAL_TURN_DETECTION`, `VOXTRAL_DEVICE`, `VOXTRAL_SAMPLE_RATE`,
`VOXTRAL_CHUNK_MS`, `VOXTRAL_LINES`, `VOXTRAL_FONT_SIZE`, `VOXTRAL_LOG_FILE`, `VOXTRAL_NO_OVERLAY`.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--delay-ms` | 480 | `target_streaming_delay_ms`: multiple of 80 in [80, 1200], or 2400. Lower = sooner, less accurate. |
| `--chunk-ms` | 100 | audio chunk size per `input_audio.append` |
| `--lines` | 3 | caption lines shown in the overlay |
| `--font-size` | 28 | overlay font size in px |
| `--turn-detection` | off | emit `turn.*` events; caption line closes at `turn.end` (incompatible with `--diarize`) |
| `--diarize` | off | `transcription.segment` events with `speaker_id` |
| `--max-retries` | 5 | WebSocket reconnects with backoff before giving up |

## Development

```bash
pip install -e ".[test]"
pytest    # 30 tests: protocol, config, subtitle buffer, transcriber vs a loopback fake WebSocket server, end-to-end app run
```

The suite runs entirely on `127.0.0.1` against a fake realtime server — no API key, audio hardware,
or display needed. `sounddevice` and `PySide6` are imported lazily, so core tests run without them.

## Layout

```
src/mistral_speech_to_text/
├── protocol.py      # wire messages/events for the realtime WebSocket API
├── config.py        # Settings: CLI/env, validation, URL resolution
├── transcriber.py   # RealtimeTranscriber: session lifecycle, streaming, reconnect
├── audio.py         # mic capture (sounddevice), WAV source, resampling to 16 kHz mono
├── subtitles.py     # SubtitleBuffer: append-only deltas → rolling caption lines
├── overlay.py       # Qt transparent always-on-top click-through window / console
├── app.py           # wiring: audio → transcriber → buffer → overlay
└── cli.py           # argparse entry point (mistral-stt / python -m mistral_speech_to_text)
```

## Notes & limits

- Session settings are fixed after the first audio chunk; restart the app to change them.
- `diarize` and `turn_detection` are mutually exclusive in one session (API limitation).
- Hosted realtime transcription is billed per minute of audio (see Mistral pricing).
