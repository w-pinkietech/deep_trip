from agora_python_server_sdk import (
    AgoraService,
    AgoraServiceConfig,
    RtcConnectionConfig,
    RtcConnection,
    AudioSubscriptionOptions,
    IAudioFrameObserver,
    AudioFrame
)
import time
import asyncio
from config import AGORA_APP_ID, AGORA_APP_CERTIFICATE

class AudioObserver(IAudioFrameObserver):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_playback_audio_frame_before_mixing(self, agora_local_user, channelId, uid, audio_frame: AudioFrame):
        # This is where we get the audio data from the user
        if self.callback:
            self.callback(audio_frame.buffer, uid)
        return True

class AgoraManager:
    def __init__(self, app_id: str = AGORA_APP_ID):
        self.app_id = app_id
        self.service = None
        self.connection = None
        self.is_running = False

    def setup(self):
        config = AgoraServiceConfig()
        config.app_id = self.app_id
        config.audio_scenario = 0 # Default audio scenario
        self.service = AgoraService()
        self.service.initialize(config)

    def join_channel(self, channel_id: str, user_id: str, audio_callback):
        if not self.service:
            self.setup()

        con_config = RtcConnectionConfig()
        con_config.client_role_type = 1 # Host
        con_config.channel_profile = 1 # Live broadcasting
        
        self.connection = self.service.create_rtc_connection(con_config)
        
        # Register audio observer
        observer = AudioObserver(audio_callback)
        self.connection.get_local_user().register_audio_frame_observer(observer)
        
        # Subscribe to all audio
        sub_options = AudioSubscriptionOptions()
        sub_options.bytes_per_sample = 2
        sub_options.number_of_channels = 1
        sub_options.sample_rate_hz = 16000
        self.connection.get_local_user().subscribe_all_audio(sub_options)
        
        # Connect to channel
        # For simplicity, we assume no token is needed for the hackathon environment
        # If needed, we'll generate one
        self.connection.connect(None, channel_id, user_id)
        self.is_running = True
        print(f"Joined Agora channel: {channel_id} as {user_id}")

    def stop(self):
        if self.connection:
            self.connection.disconnect()
            self.connection.release()
        if self.service:
            self.service.release()
        self.is_running = False

# Example integration
# async def main():
#     manager = AgoraManager()
#     manager.join_channel("test-channel", "ai-agent", lambda data, uid: print(f"Received audio from {uid}"))
#     while True:
#         await asyncio.sleep(1)
