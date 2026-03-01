import json
import math
import re
import time
import uuid
import asyncio
from openai import AsyncOpenAI
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
        self.llm_client: AsyncOpenAI | None = None
        self.llm_model: str = ""
        self.system_prompt: str = ""
        self.location: tuple[float, float] | None = None
        self.conversation_history: list[dict] = []
        self.max_history: int = 20

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        # OpenClaw client
        container_name = ""
        try:
            container_name, _ = await ten_env.get_property_string("OPENCLAW_HOST")
        except Exception:
            pass
        config = OpenClawConfig()
        if container_name:
            config.container_name = container_name
        self.client = OpenClawClient(config)
        ten_env.log_info(f"OpenClaw client ready (container: {config.container_name})")

        # System prompt
        try:
            self.system_prompt, _ = await ten_env.get_property_string("SYSTEM_PROMPT")
        except Exception:
            self.system_prompt = ""

        # LLM client (OpenAI-compatible)
        api_key = ""
        base_url = ""
        model = ""
        try:
            api_key, _ = await ten_env.get_property_string("api_key")
        except Exception:
            pass
        try:
            base_url, _ = await ten_env.get_property_string("base_url")
        except Exception:
            pass
        try:
            model, _ = await ten_env.get_property_string("model")
        except Exception:
            pass

        if api_key:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm_client = AsyncOpenAI(**kwargs)
            self.llm_model = model or "gpt-4o-mini"
            ten_env.log_info(f"LLM client ready (model: {self.llm_model}, base_url: {base_url or 'default'})")
        else:
            ten_env.log_warn("No api_key configured, LLM calls will be skipped")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
        self.client = None
        self.llm_client = None

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug(f"on_cmd name {cmd_name}")

        if cmd_name == "on_user_joined":
            ten_env.log_info("User joined — sending greeting")
            asyncio.create_task(self._send_greeting(ten_env))
        elif cmd_name == "on_user_left":
            ten_env.log_info("User left")
            self.conversation_history.clear()
        elif cmd_name == "update_location":
            try:
                lat, _ = cmd.get_property_float("lat")
                lng, _ = cmd.get_property_float("lng")
                self.location = (lat, lng)
                ten_env.log_info(f"Location updated: {lat}, {lng}")
            except Exception as e:
                ten_env.log_warn(f"Failed to update location: {e}")

        cmd_result = CmdResult.create(StatusCode.OK, cmd)
        await ten_env.return_result(cmd_result)

    async def _send_greeting(self, ten_env: AsyncTenEnv) -> None:
        """Send a greeting when a user joins."""
        if not self.llm_client:
            await self._send_text_to_tts(ten_env, "こんにちは！Deep Tripへようこそ。何かお手伝いできることはありますか？")
            return

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": "ユーザーが接続しました。短く温かい挨拶をしてください。"})

        try:
            request_id = str(uuid.uuid4())
            t0 = time.monotonic()
            stream = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                max_tokens=200,
                stream=True,
            )

            full_reply = ""
            buffer = ""
            t_first_chunk = None
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                if not content:
                    continue

                if t_first_chunk is None:
                    t_first_chunk = time.monotonic()
                    ten_env.log_info(f"Greeting LLM TTFB: {(t_first_chunk - t0)*1000:.0f}ms")

                buffer += content
                clean = self._extract_non_thinking_text(buffer)
                if clean and len(clean) > len(full_reply):
                    new_text = clean[len(full_reply):]
                    full_reply = clean
                    await self._send_text_chunk_to_tts(ten_env, request_id, new_text, is_end=False)

            await self._send_text_chunk_to_tts(ten_env, request_id, "", is_end=True)
            ten_env.log_info(f"Greeting streamed ({(time.monotonic() - t0)*1000:.0f}ms): {full_reply[:80]}...")
        except Exception as e:
            ten_env.log_warn(f"Greeting LLM call failed: {e}")
            await self._send_text_to_tts(ten_env, "こんにちは！Deep Tripへようこそ。")

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug(f"on_data name {data_name}")

        if data_name == "asr_result":
            try:
                is_final, _ = data.get_property_bool("final")
                text, _ = data.get_property_string("text")

                if is_final and text:
                    ten_env.log_info(f"ASR Result: {text}")
                    asyncio.create_task(self._handle_user_query(ten_env, text))
            except Exception as e:
                ten_env.log_warn(f"Failed to parse asr_result: {e}")
        elif data_name == "data_in":
            try:
                raw, _ = data.get_property_string("data")
                payload = json.loads(raw)
                if payload.get("cmd") == "update_location":
                    lat = float(payload["lat"])
                    lng = float(payload["lng"])
                    self.location = (lat, lng)
                    ten_env.log_info(f"Location updated via data channel: {lat}, {lng}")
            except Exception as e:
                ten_env.log_warn(f"Failed to parse data channel message: {e}")

    async def _handle_user_query(self, ten_env: AsyncTenEnv, text: str) -> None:
        """Process user query: search context, call LLM, stream response to TTS."""
        t0 = time.monotonic()
        location_str = f"{self.location[0]},{self.location[1]}" if self.location else "unknown location"

        # Search for context via OpenClaw
        context_info = ""
        if self.client:
            try:
                t_search = time.monotonic()
                results = await self.client.search(text, location_str)
                ten_env.log_info(f"Search latency: {(time.monotonic() - t_search)*1000:.0f}ms")
                if results and results[0].content:
                    context_info = "\n".join([r.content for r in results if r.content])
                    ten_env.log_info(f"Found {len(results)} search results")
            except Exception as e:
                ten_env.log_warn(f"Search failed: {e}")

        # Build messages for the LLM
        messages = []
        if self.system_prompt:
            system_parts = [self.system_prompt]
            if self.location:
                system_parts.append(f"ユーザーの現在地: {location_str}")
            if context_info:
                system_parts.append(f"検索結果からの参考情報:\n{context_info}")
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        # Add conversation history
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": text})

        if not self.llm_client:
            ten_env.log_warn("No LLM client, echoing user text")
            await self._send_text_to_tts(ten_env, text)
            return

        try:
            ten_env.log_info(f"Calling LLM with {len(messages)} messages...")

            # Streaming LLM
            request_id = str(uuid.uuid4())
            t_llm = time.monotonic()
            t_first_chunk = None
            stream = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                max_tokens=500,
                stream=True,
            )

            full_reply = ""
            buffer = ""
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                if not content:
                    continue

                if t_first_chunk is None:
                    t_first_chunk = time.monotonic()
                    ten_env.log_info(f"LLM TTFB: {(t_first_chunk - t_llm)*1000:.0f}ms")

                buffer += content
                clean = self._extract_non_thinking_text(buffer)
                if clean and len(clean) > len(full_reply):
                    new_text = clean[len(full_reply):]
                    full_reply = clean
                    await self._send_text_chunk_to_tts(ten_env, request_id, new_text, is_end=False)

            # Final chunk
            await self._send_text_chunk_to_tts(ten_env, request_id, "", is_end=True)
            ten_env.log_info(f"LLM reply: {full_reply[:100]}...")
            ten_env.log_info(f"Total pipeline: {(time.monotonic() - t0)*1000:.0f}ms")

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": text})
            self.conversation_history.append({"role": "assistant", "content": full_reply})
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

        except Exception as e:
            ten_env.log_warn(f"LLM call failed: {e}")
            # Try demo fallback
            try:
                from .demo_fallback import get_fallback_response
                location_name = self._get_location_name()
                fallback = get_fallback_response(location_name, text)
                if fallback:
                    ten_env.log_info(f"Using demo fallback for {location_name}")
                    await self._send_text_to_tts(ten_env, fallback)
            except Exception:
                pass

    # Known locations for fallback matching (name, lat, lng)
    _KNOWN_LOCATIONS = [
        ("sensoji", 35.7148, 139.7967),
        ("shibuya", 35.6580, 139.7016),
        ("meiji", 35.6764, 139.6993),
    ]

    def _get_location_name(self) -> str | None:
        """Map current GPS coordinates to a known location name."""
        if not self.location:
            return None
        lat, lng = self.location
        # Find closest known location within ~500m threshold
        best_name = None
        best_dist = float("inf")
        for name, klat, klng in self._KNOWN_LOCATIONS:
            dist = math.hypot(lat - klat, lng - klng)
            if dist < best_dist:
                best_dist = dist
                best_name = name
        # ~0.005 degrees ≈ 500m
        if best_dist < 0.005:
            return best_name
        return None

    @staticmethod
    def _extract_non_thinking_text(text: str) -> str:
        """Remove complete <think>...</think> blocks and truncate at unclosed <think> tags."""
        # Remove complete thinking blocks
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # Truncate at unclosed <think> tag
        idx = cleaned.find("<think>")
        if idx != -1:
            cleaned = cleaned[:idx]
        return cleaned.strip()

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove <think>...</think> reasoning blocks from LLM output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def _send_text_chunk_to_tts(self, ten_env: AsyncTenEnv, request_id: str, text: str, is_end: bool) -> None:
        """Send an incremental text chunk to the TTS extension."""
        output_data = Data.create("tts_text_input")
        payload = json.dumps({
            "request_id": request_id,
            "text": text,
            "text_input_end": is_end,
        })
        output_data.set_property_from_json("", payload)
        await ten_env.send_data(output_data)
        if text:
            ten_env.log_debug(f"TTS chunk (req={request_id[:8]}): {text[:40]}...")

    async def _send_text_to_tts(self, ten_env: AsyncTenEnv, text: str) -> None:
        """Send text data to the TTS extension as TTSTextInput."""
        request_id = str(uuid.uuid4())
        output_data = Data.create("tts_text_input")
        payload = json.dumps({
            "request_id": request_id,
            "text": text,
            "text_input_end": True,
        })
        output_data.set_property_from_json("", payload)
        await ten_env.send_data(output_data)
        ten_env.log_info(f"Sent to TTS (req={request_id[:8]}): {text[:60]}...")

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        pass
