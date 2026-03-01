# 🎤 Deep Trip - Voice-Powered Cultural Guide

Vox Tokyo Hackathon 2024 Project
Track: ⛩️ Omotenashi AI — Real-time cultural companion for tourists in Japan

## Background & Problem
The Japan Tourism Agency has set an ambitious target of **60 million inbound visitors by 2030**. While the number of visitors is recovering rapidly—reaching **25.07 million in 2023** and projected to exceed **35 million in 2024**—a critical challenge remains in regional tourism. The government aims to increase the **average length of stay in regional areas to 3 days**, but the current average remains **less than 2 days**.

Japan has many hidden gems, but they are often not sufficiently explained in foreign languages. Additionally, due to language barriers, local residents often miss opportunities to convey the charm of their hometowns to international travelers. This information gap contributes to the concentration of tourists in major cities and shorter stays in regional areas.

## Value Proposition
**"The joy of suddenly receiving an explanation about where you are from the app."**

Deep Trip verbalizes the deep charm of each location—nuances that even Japanese people might miss—through the power of technology and delivers it to travelers.

## Solution
Deep Trip is a tool designed to solve these challenges. By utilizing location data to provide real-time, multi-lingual explanations of local culture and history, it enhances the satisfaction of regional stays and contributes to extending the duration of visits.

Technically, Deep Trip is a voice-powered AI assistant built as a **TEN Framework Extension**. It provides real-time cultural and historical information about your current location in Japan. The system uses the TEN Framework's graph architecture to connect ASR, LLM, TTS, and our custom "Cultural Guide" logic.

### Core Features
- **Location-Aware**: Uses your GPS location to identify where you are.
- **Real-Time Knowledge**: Searches the internet in real-time for cultural/historical information.
- **Cultural Whisperer**: Explains it naturally in Japanese/English with MiniMax's emotionally expressive voice.
- **Omotenashi Guide**: Provides cultural etiquette tips and local insights on-the-spot.

## Technology Stack
- **Framework**: [TEN Framework](https://github.com/TEN-framework/ten-framework) (Python Extension)
- **AI Models**: 
  - **LLM**: MiniMax M2.5 (Intelligence & Reasoning)
  - **TTS**: MiniMax Speech (Japanese/English)
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
