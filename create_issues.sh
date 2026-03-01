#!/bin/bash

# Function to create an issue
create_issue() {
  local title="$1"
  local body="$2"
  echo "Creating issue: $title"
  gh issue create --title "$title" --body "$body"
}

# Phase 1
create_issue "Phase 1: Initialize TEN Extension" "Initialize the project using 'tman create extension deep_trip_extension --template default_extension_python'. Set up manifest.json and property.json."
create_issue "Phase 1: Dependency Management" "Define requirements.txt with necessary libraries (aiohttp, cryptography for OpenClaw, requests for Whisper)."

# Phase 2
create_issue "Phase 2: OpenClaw Integration" "Implement OpenClawClient class to handle WebSocket handshake, Ed25519 authentication, and chat.send protocol. Connect to local Docker instance."
create_issue "Phase 2: Omotenashi Persona Design" "Refine system_prompt for MiniMax M2.5. Ensure 'Hospitality' tone (polite Japanese, cultural context)."
create_issue "Phase 2: Context Manager" "Implement logic to combine User Query + GPS Location -> OpenClaw Search -> Summary -> LLM Response."

# Phase 3
create_issue "Phase 3: Extension Logic Implementation" "Implement on_cmd in extension.py to handle incoming text/voice commands. Connect the 'Brain' to the TEN runtime."
create_issue "Phase 3: Graph Construction" "Design the data flow: Whisper ASR -> Deep Trip Extension -> MiniMax TTS. Configure graph.json / property.json."

# Phase 4
create_issue "Phase 4: Whisper ASR Client" "Implement a client to send audio to http://100.124.66.113:9000. Handle audio buffering and silence detection if needed."
create_issue "Phase 4: TTS Integration" "Ensure MiniMax TTS receives the text stream from our extension. Tune TTS parameters for emotional expression."

# Phase 5
create_issue "Phase 5: Frontend/Demo UI" "Create a simple mechanism (Web UI or mock script) to send GPS coordinates to the extension. Minimal web page showing status."

# Phase 6
create_issue "Phase 6: End-to-End Testing" "Verify latency (aiming for real-time). Test cultural accuracy of responses."
