# Deep Trip - Hackathon Demo Script (3 minutes)

## Pre-Demo Checklist

- [ ] Run preflight check: `python demo/preflight_check.py`
- [ ] Docker Desktop running with OpenClaw container up
- [ ] TEN runtime started (`task run` or Docker Compose)
- [ ] Test client open in browser: `test_client/index.html`
- [ ] `.env` file populated with all required keys (see `.env.example`)
- [ ] Microphone and speakers tested
- [ ] Browser tab with test client in focus, log panel visible

---

## Scene 1: Connect & Greeting (30 seconds)

**Action:** Click "Join Channel" in the test client.

**Expected:** The agent connects via Agora RTC, Deepgram ASR activates, and the AI guide greets the user in Japanese with a warm omotenashi-style welcome.

**Talking point:** "Deep Trip is a real-time voice-guided cultural tour of Japan. The moment you connect, our AI guide greets you — powered by MiniMax M2.5 for natural Japanese with emotional expression."

---

## Scene 2: Senso-ji Temple (60 seconds)

**Action:** Select "Senso-ji Temple" from the location dropdown.

**Say:** "この場所について教えてください" (Tell me about this place)

**Expected:** The agent uses OpenClaw to search for cultural context about Senso-ji, then responds with historical and cultural information about the temple — Kaminarimon gate, Nakamise-dori, the incense hall.

**Follow-up — Say:** "参拝のマナーを教えてください" (Tell me about visiting etiquette)

**Expected:** The agent explains proper temple etiquette — bowing, hand washing at the temizuya, how to pray, and incense purification.

**Talking point:** "The guide uses location-aware context from OpenClaw to provide accurate, real-time cultural information. Notice the response latency — under 2-3 seconds from speech to voice reply."

---

## Scene 3: Shibuya Crossing (60 seconds)

**Action:** Select "Shibuya Crossing" from the location dropdown.

**Say:** "渋谷のスクランブル交差点はどんなところですか？" (What is the Shibuya scramble crossing like?)

**Expected:** The agent describes the world-famous crossing — the volume of pedestrians, the surrounding screens, the energy of the area.

**Follow-up — Say:** "ハチ公について教えて" (Tell me about Hachiko)

**Expected:** The agent tells the story of Hachiko the loyal dog, the statue's location, and its cultural significance.

**Talking point:** "When we switch locations, the guide seamlessly adapts. It pulls fresh context from OpenClaw and maintains conversation history — it remembers what we just discussed."

---

## Scene 4: Hidden Gem (30 seconds)

**Say:** "この近くで、あまり知られていないおすすめの場所はありますか？" (Are there any lesser-known recommended places nearby?)

**Expected:** The agent recommends a hidden gem near Shibuya — perhaps a quiet shrine, a back-alley izakaya street, or a rooftop garden.

**Talking point:** "This is the omotenashi difference — our guide doesn't just recite Wikipedia. It recommends hidden gems that locals know, going beyond standard guidebook content."

---

## Key Talking Points

| Feature | Detail |
|---------|--------|
| **Real-time voice** | End-to-end latency under 2-3 seconds (speech → ASR → LLM → TTS → audio) |
| **Location-aware** | GPS coordinates sent via Agora data channel; OpenClaw provides cultural context |
| **Omotenashi persona** | Warm, polite Japanese guide persona with emotional expression |
| **MiniMax M2.5** | Reasoning + natural Japanese TTS in a single model stack |
| **Streaming responses** | LLM streams tokens to TTS for faster time-to-first-audio |
| **Search caching** | Repeated queries served from LRU cache (50 entries, 5-min TTL) |
| **TEN Framework** | Graph-based extension architecture for modular real-time AI agents |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No audio from agent | Check TTS API key in `.env`, verify MiniMax TTS container logs |
| Agent not responding | Check Deepgram ASR key, verify microphone permissions in browser |
| Slow responses (>5s) | OpenClaw may be cold-starting; repeat the query (cache will kick in) |
| "Connection failed" | Verify Agora APP_ID, check TEN runtime is running |
| OpenClaw errors | Run `docker ps` to confirm container is up; run `docker logs <container>` |
| Location not updating | Ensure you selected a preset or granted GPS permission |
| Fallback responses | If LLM is down, the system uses cached fallback responses automatically |
