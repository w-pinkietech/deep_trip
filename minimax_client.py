import httpx
import os
import json
import base64
from typing import Optional
from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, DEFAULT_VOICE_ID

class MiniMaxClient:
    def __init__(self, api_key: str = MINIMAX_API_KEY, group_id: str = MINIMAX_GROUP_ID):
        self.api_key = api_key
        self.group_id = group_id
        self.base_url = "https://api.minimax.chat/v1/text_to_speech"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def synthesize(self, text: str, voice_id: str = DEFAULT_VOICE_ID) -> Optional[bytes]:
        """
        Synthesize text to speech using MiniMax API.
        Returns the audio content as bytes.
        """
        if not self.api_key or not self.group_id:
            print("MiniMax API Key or Group ID is not set.")
            return None

        payload = {
            "voice_id": voice_id,
            "text": text,
            "model": "speech-01-turbo", # 高速・低遅延モデル
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
            "emotion": "happy", # デフォルトの感情
            "output_format": "mp3"
        }

        # Query parameter required for MiniMax
        url = f"{self.base_url}?GroupId={self.group_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload, timeout=10.0)
                if response.status_code == 200:
                    # Check if the response is JSON (error) or binary (audio)
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        result = response.json()
                        if result.get("base_resp", {}).get("status_code") != 0:
                            print(f"MiniMax Error: {result.get('base_resp', {}).get('status_msg')}")
                            return None
                        # Some versions return base64 audio in JSON
                        if "data" in result and "audio" in result["data"]:
                            return base64.b64decode(result["data"]["audio"])
                    return response.content
                else:
                    print(f"MiniMax API Error: {response.status_code} - {response.text}")
                    return None
            except Exception as e:
                print(f"MiniMax synthesis failed: {e}")
                return None

# Usage example
# client = MiniMaxClient()
# audio_bytes = await client.synthesize("こんにちは、今日はどちらへ行かれますか？")
