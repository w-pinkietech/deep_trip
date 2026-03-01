from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import asyncio
from dotenv import load_dotenv
from config import OMOTENASHI_SYSTEM_PROMPT, AGORA_APP_ID
from minimax_client import MiniMaxClient
from agora_manager import AgoraManager

load_dotenv()

app = FastAPI(title="Deep Trip - Voice Travel Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
minimax = MiniMaxClient()
agora = AgoraManager(app_id=AGORA_APP_ID)

@app.get("/")
async def root():
    return {
        "message": "🎤 Deep Trip Voice Assistant is running!",
        "status": "ready",
        "track": "Omotenashi AI"
    }

@app.post("/start-voice")
async def start_voice(channel_id: str, user_id: str):
    """
    Join an Agora channel to start real-time voice interaction.
    """
    def handle_audio(data, uid):
        # Here we would send data to STT and then to LLM
        print(f"Received {len(data)} bytes of audio from {uid}")
        # Placeholder for STT -> LLM -> TTS loop
        pass

    agora.join_channel(channel_id, user_id, handle_audio)
    return {"message": f"Joined channel {channel_id} successfully"}

@app.post("/stop-voice")
async def stop_voice():
    agora.stop()
    return {"message": "Voice interaction stopped"}

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        # Initial greeting from the Omotenashi AI
        greeting = "こんにちは！おもてなしガイドのDeep Tripです。今日はどのような旅のお手伝いをしましょうか？"
        audio_content = await minimax.synthesize(greeting)
        if audio_content:
            # Send greeting as audio or text for now
            await websocket.send_text(f"AI: {greeting}")
            # In a real demo, we'd send the audio stream back via Agora or WebSocket
        
        while True:
            # Receive text input for now (as a fallback/demo)
            data = await websocket.receive_text()
            print(f"User message: {data}")
            
            # Simple LLM logic (mock for now, focusing on persona)
            response_text = f"『{data}』についてですね。承知いたしました。日本の隠れた魅力を、おもてなしの心でご案内します。"
            
            # Synthesize response
            audio_response = await minimax.synthesize(response_text)
            
            if audio_response:
                # For demo purposes, we send the text back
                await websocket.send_text(f"AI: {response_text}")
                # In a full implementation, we would push audio_response to the Agora stream
            else:
                await websocket.send_text(f"AI (Text only): {response_text}")

    except Exception as e:
        print(f"Connection closed: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
