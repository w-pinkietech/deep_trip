import json
from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
    AudioFrame,
    VideoFrame,
)
from .openclaw_client import OpenClawClient, OpenClawConfig

class DeepTripExtension(AsyncExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.client: OpenClawClient | None = None
        self.location: tuple[float, float] | None = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        
        # Read properties
        # Note: property keys should match property.json
        gateway_url = await ten_env.get_property_string("OPENCLAW_HOST")
        if not gateway_url:
            gateway_url = "ws://localhost:8000"
            
        config = OpenClawConfig(
            gateway_url=gateway_url,
            # Add other properties as needed
        )
        
        self.client = OpenClawClient(config)
        try:
            await self.client.start()
            ten_env.log_info("OpenClaw client started")
        except Exception as e:
            ten_env.log_error(f"Failed to start OpenClaw client: {e}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
        if self.client:
            await self.client.stop()
            self.client = None

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug(f"on_cmd name {cmd_name}")

        if cmd_name == "on_user_joined":
            ten_env.log_info("User joined")
        elif cmd_name == "on_user_left":
            ten_env.log_info("User left")
        elif cmd_name == "update_location":
            try:
                lat = cmd.get_property_float("lat")
                lng = cmd.get_property_float("lng")
                self.location = (lat, lng)
                ten_env.log_info(f"Location updated: {lat}, {lng}")
            except Exception as e:
                ten_env.log_warn(f"Failed to update location: {e}")

        cmd_result = CmdResult.create(StatusCode.OK, cmd)
        await ten_env.return_result(cmd_result)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug(f"on_data name {data_name}")

        if data_name == "asr_result":
            try:
                # Properties on Data object are accessed synchronously
                is_final = data.get_property_bool("is_final")
                text = data.get_property_string("text")
                
                if is_final and text:
                    ten_env.log_info(f"ASR Result: {text}")
                    location_str = f"{self.location[0]},{self.location[1]}" if self.location else "unknown location"
                    
                    context_info = ""
                    if self.client:
                        try:
                            results = await self.client.search(text, location_str)
                            if results:
                                context_info = "\n".join([r.content for r in results])
                                ten_env.log_info(f"Found {len(results)} search results")
                        except Exception as e:
                            ten_env.log_warn(f"Search failed: {e}")

                    enriched_text = text
                    if context_info:
                        enriched_text = f"Context from OpenClaw:\n{context_info}\n\nUser Query: {text}"

                    output_data = Data.create("text_data")
                    output_data.set_property_string("text", enriched_text)
                    output_data.set_property_bool("is_final", True)
                    await ten_env.send_data(output_data)
            except Exception as e:
                ten_env.log_warn(f"Failed to parse asr_result: {e}")

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug(f"on_audio_frame name {audio_frame_name}")

        # TODO: process audio frame

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug(f"on_video_frame name {video_frame_name}")

        # TODO: process video frame
