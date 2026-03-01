# Deep Trip - Voice-Powered Cultural Guide

Vox Tokyo Hackathon 2024 Project
Track: Omotenashi AI -- Real-time cultural companion for tourists in Japan

## Architecture

```
[Agora RTC] -> [Deepgram ASR] -> [Deep Trip Extension] -> [MiniMax M2.5 LLM] -> [MiniMax TTS] -> [Agora RTC]
                                         |
                                   [OpenClaw Search]
                                   (Docker CLI)
```

**Built-in TEN extensions** (no custom code): `agora_rtc`, `deepgram_asr_python`, `openai_llm2_python`, `minimax_tts_websocket_python`, `streamid_adapter`

**Custom extension** (what we build): `deep_trip` -- cultural guide orchestrator

## Project Structure

```
deep_trip/
  extension.py          # Core DeepTripExtension (streaming LLM, location, search)
  openclaw_client.py    # OpenClaw Docker CLI wrapper with LRU cache
  addon.py              # TEN addon registration
  demo_fallback.py      # Cached responses for demo reliability
  manifest.json         # Extension metadata & API schema
  tests/                # Unit + integration + cultural accuracy tests
tenapp/
  main.go               # Go entry point
  manifest.json         # App dependencies
  property.json         # Graph definition & node config
  bin/main              # Built binary
  ten_packages/         # Installed TEN extensions & system packages
test_client/
  index.html            # Demo UI (Agora + GPS + transcript + status)
  server.py             # HTTPS server with token generation
scripts/
  verify_minimax.py     # MiniMax M2.5 API verification
  send_location.py      # Mock GPS location sender
  measure_latency.py    # Latency benchmarking
demo/
  demo_script.md        # 3-minute hackathon demo script
  preflight_check.py    # Pre-demo service validation
```

## Quick Start

### Prerequisites

- **Python 3.10** (required -- TEN runtime links against libpython3.10)
- **Go 1.23+**
- **Docker** (for OpenClaw)
- **tman** (TEN package manager)

### 1. Clone and configure

```bash
git clone <repo-url> && cd deep_trip
cp .env.example .env
# Fill in: OPENAI_API_KEY, DEEPGRAM_API_KEY, AGORA_APP_ID,
#   AGORA_APP_CERTIFICATE, MINIMAX_TTS_API_KEY, MINIMAX_TTS_GROUP_ID
```

### 2. Start OpenClaw

```bash
# In your openclaw directory:
docker compose up -d
```

### 3. Build and run (first time)

```bash
./setup_and_run.sh all
```

This installs Go, tman, builds the TEN app, and starts it. For subsequent runs:

```bash
./setup_and_run.sh run
```

### 4. Start the demo UI (separate terminal)

```bash
cd test_client
python3.10 server.py
```

### 5. Open the demo

Open `https://localhost:3000` (or `https://<tailscale-ip>:3000` for remote).
Accept the self-signed certificate, click "Join Channel", and start talking.

## Important: Python 3.10 Requirement

The TEN runtime's Python addon loader (`libpython_addon_loader.so`) links against
`libpython3.10.so`. This means:

- All Python packages must be installed via `python3.10 -m pip install ...`
- Do NOT use pyenv Python 3.12 or other versions
- The `setup_and_run.sh` script handles this automatically

## Environment Variables

The `setup_and_run.sh run` command automatically sets these critical paths:

| Variable | Purpose |
|----------|---------|
| `PYTHONPATH` | Adds `ten_ai_base/interface` and `ten_runtime_python/interface` so TEN system packages are importable |
| `LD_LIBRARY_PATH` | Adds `agora_rtc_sdk/lib` so `libagora_rtc_sdk.so` is found at runtime |

Running the binary directly without these will fail with `ModuleNotFoundError` or `dlopen` errors.

## Running Tests

```bash
python3.10 -m pytest deep_trip/tests/ -v
```

## Demo

See [demo/demo_script.md](demo/demo_script.md) for the full 3-minute hackathon demo script.

Pre-flight check: `python3.10 demo/preflight_check.py`

## Technology Stack

- **Framework**: [TEN Framework](https://github.com/TEN-framework/ten-framework)
- **LLM**: MiniMax M2.5 (via OpenAI-compatible API)
- **TTS**: MiniMax Speech WebSocket
- **ASR**: Deepgram (nova-3)
- **Audio Transport**: Agora RTC
- **Search**: OpenClaw (Docker CLI)
