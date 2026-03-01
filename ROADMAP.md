# Deep Trip Development Roadmap

## Architecture Overview

```
[Agora RTC] -> [Deepgram ASR] -> [Deep Trip Extension] -> [OpenAI LLM (MiniMax M2.5)] -> [MiniMax TTS] -> [Agora RTC]
                                                |
                                         [OpenClaw Search]
                                         (local Docker)
```

**Built-in TEN extensions (no custom code needed):**
- `agora_rtc` — audio transport
- `deepgram_asr_python` — Deepgram ASR (speech-to-text)
- `openai_llm2_python` — LLM via OpenAI-compatible API (pointed at MiniMax M2.5)
- `minimax_tts_websocket_python` — MiniMax TTS (text-to-speech)
- `streamid_adapter` — stream routing

**Custom extension (what we build):**
- `deep_trip` — cultural guide orchestrator: receives ASR text + GPS location, queries OpenClaw for cultural context, assembles enriched prompt, forwards to LLM

---

## Phase 1: Project Setup

- [ ] **Scaffold Deep Trip extension**
  - Create extension directory at repo root: `deep_trip/`
  - Files: `extension.py`, `addon.py`, `__init__.py`, `manifest.json`, `property.json`, `requirements.txt`
  - Register addon as `deep_trip` via `@register_addon_as_extension`
  - Inherit from `AsyncExtension`
- [ ] **Integrate with ten-framework submodule**
  - Symlink or path-reference `deep_trip/` from `ten-framework/ai_agents/agents/ten_packages/extension/`
  - Add dependency in tenapp `manifest.json`
- [x] **Dependencies**
  - No special SDK needed — OpenClaw is accessed via `docker exec` CLI commands
  - No SDK needed for ASR/TTS/LLM (handled by existing TEN extensions)
- [ ] **Environment config**
  - Create `.env.example` with required variables:
    - `DEEPGRAM_API_KEY`
    - `OPENAI_API_KEY` (or MiniMax API key if OpenAI-compatible endpoint)
    - `MINIMAX_TTS_API_KEY`, `MINIMAX_TTS_GROUP_ID`
    - `AGORA_APP_ID`
    - `OPENCLAW_HOST`, `OPENCLAW_PORT`

## Phase 2: OpenClaw Search Client

- [x] **Implement `OpenClawClient` class**
  - Executes CLI commands via `docker exec` against the `openclaw-test-openclaw-gateway-1` container
  - Runs `npx openclaw <subcommand>` (agent, message send, memory search, health, devices, etc.)
  - No WebSocket or auth handshake needed — the CLI handles authentication internally
- [x] **Async interface**
  - `async def search(query, location)` — sends prompt via `openclaw agent` and returns `list[SearchResult]`
  - `async def agent(message, ...)` — run an agent turn with session/channel options
  - `async def send_message(target, message, ...)` — send via chat channel
  - `async def memory_search(query, ...)` — search memory files
  - `async def health()` / `async def devices_list()` / `async def devices_approve()`
  - Timeout handling via `asyncio.wait_for` (kills subprocess on timeout)
- [x] **Unit tests**
  - Mock `asyncio.create_subprocess_exec` for all CLI operations
  - Test exec, JSON parsing, timeout/kill, all high-level methods, extract_text/extract_timestamp

## Phase 3: Deep Trip Extension (Core Logic)

- [ ] **Extension lifecycle**
  - `on_start`: initialize OpenClawClient with container name from properties
  - `on_stop`: clear client reference (no connection to close)
  - `on_cmd`: handle `on_user_joined`, `on_user_left`
  - `on_data`: receive `asr_result` from Deepgram ASR
- [ ] **Location state management**
  - Store current GPS coordinates (received via cmd or data from frontend)
  - `on_cmd("update_location")`: update lat/lng
- [ ] **Context assembly pipeline**
  - On receiving `asr_result`:
    1. Extract transcribed text
    2. Query OpenClaw with text + current GPS location
    3. Build enriched prompt: system_prompt + location context + search results + user query
    4. Send as `data("text_data")` to LLM extension
- [ ] **Omotenashi system prompt**
  - Design system prompt for MiniMax M2.5
  - Persona: polite Japanese cultural guide (omotenashi tone)
  - Instructions: use search results to provide accurate cultural/historical info
  - Format: natural conversational Japanese with cultural etiquette tips

## Phase 4: Graph Configuration

- [ ] **Create tenapp for Deep Trip**
  - `tenapp/main.go` (or reuse existing voice-assistant tenapp)
  - `tenapp/manifest.json` with all extension dependencies
  - `tenapp/property.json` with graph definition
- [ ] **Graph wiring**
  - Define `predefined_graphs` with nodes:
    - `agora_rtc` (audio I/O)
    - `deepgram_asr_python` (Deepgram STT)
    - `deep_trip` (our extension — orchestrator)
    - `openai_llm2_python` (MiniMax M2.5 via OpenAI-compatible endpoint)
    - `minimax_tts_websocket_python` (TTS)
  - Define connections:
    - `agora_rtc` audio_frame -> `deepgram_asr_python`
    - `deepgram_asr_python` data(asr_result) -> `deep_trip`
    - `deep_trip` data(text_data) -> `openai_llm2_python`
    - `openai_llm2_python` data -> `minimax_tts_websocket_python`
    - `minimax_tts_websocket_python` audio_frame -> `agora_rtc`
- [ ] **Verify MiniMax M2.5 OpenAI-compatible endpoint**
  - Confirm API base URL, model name, auth header format
  - Test with `openai_llm2_python` extension config

## Phase 5: Frontend & Location

- [ ] **Location input mechanism**
  - Cmd endpoint to receive GPS coordinates (lat/lng)
  - Option A: Web UI with geolocation API (`navigator.geolocation`)
  - Option B: Mock script sending coordinates via API
- [ ] **Demo UI**
  - Extend TEN Agent playground or build minimal page
  - Show: current location, listening status, conversation transcript
  - Send location updates to Deep Trip extension

## Phase 6: End-to-End Testing & Demo

- [ ] **Integration testing**
  - Test full pipeline: voice input -> ASR -> Deep Trip -> LLM -> TTS -> voice output
  - Verify OpenClaw search returns relevant cultural data
- [ ] **Latency optimization**
  - Measure end-to-end latency (target: real-time conversational)
  - Profile OpenClaw search time, LLM response time
  - Consider streaming LLM response to TTS
- [ ] **Cultural accuracy testing**
  - Test with real Tokyo locations (temples, stations, neighborhoods)
  - Verify omotenashi tone and cultural correctness
- [ ] **Hackathon demo preparation**
  - Prepare demo script with specific locations
  - Fallback plan if OpenClaw is slow (cached responses)
