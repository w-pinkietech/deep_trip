# 🎤 Deep Trip - Voice-Powered Cultural Guide

Vox Tokyo Hackathon 2024 Project
Track: ⛩️ Omotenashi AI — Real-time cultural companion for tourists in Japan

## Project Overview
Deep Trip is a voice-powered AI assistant built as a **TEN Framework Extension**. It provides real-time cultural and historical information about your current location in Japan.
The system uses the TEN Framework's graph architecture to connect ASR, LLM, TTS, and our custom "Cultural Guide" logic.

## Core Concept
**"Your Personal Cultural Whisperer"**
- Uses your GPS location to identify where you are
- Searches the internet in real-time for cultural/historical information
- Explains it naturally in Japanese with MiniMax's emotionally expressive voice
- Provides cultural etiquette tips and local insights on-the-spot

## Technology Stack
- **Framework**: [TEN Framework](https://github.com/TEN-framework/ten-framework) (Python Extension)
- **AI Models**: 
  - **LLM**: MiniMax M2.5 (Intelligence & Reasoning)
  - **TTS**: MiniMax Speech (Japanese)
  - **ASR**: Local Whisper / Deepgram
- **Development Tools**: `tman` (TEN Manager), Python 3.10+

## Development Guide

This project is developed as a custom **TEN Agent Extension** in Python.

### 1. Prerequisites
Ensure you have the TEN Framework tools installed:
```bash
# Verify tman installation
tman --version
# Expected: TEN Framework version: <version>
```

### 2. Create Extension Project
We use the official Python template to scaffold the extension:

```bash
# Create the project structure
tman create extension deep_trip_extension --template default_extension_python
```

### 3. Project Structure
The generated extension follows the standard TEN directory structure:
```
deep_trip_extension/
├── manifest.json         # Metadata, dependencies, and interface definitions
├── property.json         # Configuration (API keys, default prompts)
├── requirements.txt      # Python dependencies (e.g., requests, beautifulsoup4)
├── src/
│   ├── main.py           # Entry point
│   └── extension.py      # Core Logic: Location handling & Web Search
├── tests/
│   └── test_basic.py     # Unit tests
└── .vscode/              # Debug configurations
```

### 4. Implementation Steps

#### Step A: Install Dependencies
```bash
cd deep_trip_extension
tman install --standalone
```

#### Step B: Core Logic (`src/extension.py`)
We implement the `DeepTripExtension` class inheriting from `AsyncExtension`.
Key responsibilities:
1.  Receive `on_cmd` (User Voice/Text + Location Data)
2.  Perform Real-time Web Search (Google Places / Wikipedia API)
3.  Generate "Omotenashi" response using MiniMax LLM
4.  Send text back to TTS extension

#### Step C: Configuration (`property.json`)
Define necessary properties for the extension:
```json
{
  "minimax_api_key": "",
  "google_maps_api_key": "",
  "system_prompt": "You are an Omotenashi guide..."
}
```

### 5. Build & Test
Verify the extension logic in isolation before integrating into the full graph.
```bash
# Run unit tests
tman run test
```

### 6. Integration (Graph)
To run the full assistant, we configure the TEN Agent graph to include:
`[ASR] -> [Deep Trip Extension] -> [TTS]`

## Reference
- [TEN Framework Extension Development Guide](https://github.com/TEN-framework/ten-framework/blob/main/docs/development/how_to_develop_with_ext.md)
- [MiniMax API Documentation](https://platform.minimaxi.com/)
