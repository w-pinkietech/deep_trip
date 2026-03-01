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

        # Read container name from properties (falls back to default)
        container_name = ""
        try:
            container_name = await ten_env.get_property_string("OPENCLAW_HOST")
        except Exception:
            pass

        config = OpenClawConfig()
        if container_name:
            config.container_name = container_name

        self.client = OpenClawClient(config)
        ten_env.log_info(f"OpenClaw client ready (container: {config.container_name})")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
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
                            if results and results[0].content:
                                context_info = "\n".join([r.content for r in results])
                                ten_env.log_info(f"Found {len(results)} search results")
                        except Exception as e:
                            ten_env.log_warn(f"Search failed: {e}")

                    # Assemble enriched prompt
                    prompt_parts = []
                    
                    # System prompt
                    try:
                        system_prompt = await ten_env.get_property_string("SYSTEM_PROMPT")
                    except Exception:
                        system_prompt = ""
                    if system_prompt:
                        prompt_parts.append(f"System Instructions:\n{system_prompt}")
                    
                    # Location context
                    if self.location:
                        prompt_parts.append(f"Current User Location: {location_str}")
                    
                    # Search context
                    if context_info:
                        prompt_parts.append(f"Context from Search:\n{context_info}")
                    
                    # User query
                    prompt_parts.append(f"User Query: {text}")
                    
                    enriched_text = "\n\n".join(prompt_parts)

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
