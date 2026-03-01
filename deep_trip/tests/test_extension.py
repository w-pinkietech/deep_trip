import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from deep_trip.extension import DeepTripExtension
from deep_trip.openclaw_client import SearchResult


# ---------------------------------------------------------------------------
# Mock helpers for TEN runtime objects
# ---------------------------------------------------------------------------

def make_ten_env():
    """Create a mock AsyncTenEnv."""
    env = AsyncMock()
    env.log_debug = MagicMock()
    env.log_info = MagicMock()
    env.log_warn = MagicMock()
    env.log_error = MagicMock()

    # Property storage for get_property_string / get_property_float
    _props = {}

    async def get_property_string(key):
        if key in _props:
            return (_props[key], None)
        raise Exception(f"Property {key} not found")

    env.get_property_string = AsyncMock(side_effect=get_property_string)
    env.return_result = AsyncMock()
    env.send_data = AsyncMock()

    # Attach internal store for test setup
    env._props = _props
    return env


def make_cmd(name, **properties):
    """Create a mock Cmd with given name and properties."""
    cmd = MagicMock()
    cmd.get_name = MagicMock(return_value=name)

    def get_property_float(key):
        if key not in properties:
            raise ValueError(f"Property {key} not found")
        return (float(properties[key]), None)

    cmd.get_property_float = MagicMock(side_effect=get_property_float)
    return cmd


def make_data(name, **properties):
    """Create a mock Data with given name and properties.

    Returns (value, error) tuples to match the TEN runtime API.
    """
    data = MagicMock()
    data.get_name = MagicMock(return_value=name)

    def get_property_bool(key):
        return (bool(properties.get(key, False)), None)

    def get_property_string(key):
        return (str(properties.get(key, "")), None)

    data.get_property_bool = MagicMock(side_effect=get_property_bool)
    data.get_property_string = MagicMock(side_effect=get_property_string)
    return data


class MockStream:
    """Async iterable that yields streaming LLM chunks."""
    def __init__(self, texts):
        self._texts = texts

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for text in self._texts:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            yield chunk


def make_streaming_llm(texts):
    """Create a mock LLM client that returns a stream of text chunks."""
    mock_llm = AsyncMock()
    mock_llm.chat.completions.create = AsyncMock(
        return_value=MockStream(texts)
    )
    return mock_llm


# ---------------------------------------------------------------------------
# on_init
# ---------------------------------------------------------------------------

class TestOnInit:
    @pytest.mark.asyncio
    async def test_on_init(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        await ext.on_init(ten_env)
        ten_env.log_debug.assert_called()


# ---------------------------------------------------------------------------
# on_cmd
# ---------------------------------------------------------------------------

class TestOnCmd:
    @pytest.mark.asyncio
    async def test_on_user_joined(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        cmd = make_cmd("on_user_joined")

        with patch("deep_trip.extension.CmdResult") as MockCmdResult, \
             patch.object(ext, "_send_greeting", new_callable=AsyncMock) as mock_greeting:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)
            await asyncio.sleep(0)

        ten_env.log_info.assert_any_call("User joined \u2014 sending greeting")
        ten_env.return_result.assert_awaited_once()
        mock_greeting.assert_awaited_once_with(ten_env)

    @pytest.mark.asyncio
    async def test_on_user_left(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        cmd = make_cmd("on_user_left")

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        ten_env.log_info.assert_any_call("User left")

    @pytest.mark.asyncio
    async def test_on_user_left_clears_history(self):
        ext = DeepTripExtension("test")
        ext.conversation_history = [{"role": "user", "content": "hi"}]
        ten_env = make_ten_env()
        cmd = make_cmd("on_user_left")

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        assert ext.conversation_history == []

    @pytest.mark.asyncio
    async def test_update_location(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        cmd = make_cmd("update_location", lat=35.6762, lng=139.6503)

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        assert ext.location == (35.6762, 139.6503)
        ten_env.log_info.assert_any_call("Location updated: 35.6762, 139.6503")

    @pytest.mark.asyncio
    async def test_update_location_invalid_property(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        cmd = MagicMock()
        cmd.get_name = MagicMock(return_value="update_location")
        cmd.get_property_float = MagicMock(side_effect=ValueError("missing"))

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        assert ext.location is None
        ten_env.log_warn.assert_called()

    @pytest.mark.asyncio
    async def test_unknown_cmd(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        cmd = make_cmd("unknown_command")

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        ten_env.return_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cmd_always_returns_result(self):
        """Every command should return a CmdResult regardless of cmd name."""
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()

        for cmd_name in ["on_user_joined", "on_user_left", "update_location", "anything"]:
            ten_env.return_result.reset_mock()
            cmd = make_cmd(cmd_name, lat=0.0, lng=0.0)
            with patch("deep_trip.extension.CmdResult") as MockCmdResult, \
                 patch.object(ext, "_send_greeting", new_callable=AsyncMock):
                MockCmdResult.create.return_value = MagicMock()
                await ext.on_cmd(ten_env, cmd)
            ten_env.return_result.assert_awaited_once()


# ---------------------------------------------------------------------------
# on_data (ASR processing pipeline)
# ---------------------------------------------------------------------------

class TestOnData:
    @pytest.mark.asyncio
    async def test_non_asr_data_ignored(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("some_other_data", text="hello")

        await ext.on_data(ten_env, data)

        ten_env.send_data.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_final_asr_ignored(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", final=False, text="partial")

        with patch.object(ext, "_handle_user_query", new_callable=AsyncMock) as mock_handle:
            await ext.on_data(ten_env, data)
            await asyncio.sleep(0)
            mock_handle.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", final=True, text="")

        with patch.object(ext, "_handle_user_query", new_callable=AsyncMock) as mock_handle:
            await ext.on_data(ten_env, data)
            await asyncio.sleep(0)
            mock_handle.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_final_asr_creates_query_task(self):
        """Final ASR with text should trigger _handle_user_query via create_task."""
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", final=True, text="Tell me about this place")

        with patch.object(ext, "_handle_user_query", new_callable=AsyncMock) as mock_handle:
            await ext.on_data(ten_env, data)
            await asyncio.sleep(0)
            mock_handle.assert_awaited_once_with(ten_env, "Tell me about this place")

    @pytest.mark.asyncio
    async def test_asr_logs_text(self):
        """Final ASR result should log the recognized text."""
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", final=True, text="Hello world")

        with patch.object(ext, "_handle_user_query", new_callable=AsyncMock):
            await ext.on_data(ten_env, data)

        ten_env.log_info.assert_any_call("ASR Result: Hello world")

    @pytest.mark.asyncio
    async def test_data_in_location_update(self):
        """data_in with update_location command should update location."""
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        payload = json.dumps({"cmd": "update_location", "lat": 35.6762, "lng": 139.6503})
        data = make_data("data_in", data=payload)

        await ext.on_data(ten_env, data)

        assert ext.location == (35.6762, 139.6503)


# ---------------------------------------------------------------------------
# _handle_user_query (streaming LLM pipeline)
# ---------------------------------------------------------------------------

class TestHandleUserQuery:
    @pytest.mark.asyncio
    async def test_query_without_llm_echoes_text(self):
        """Without an LLM client, _handle_user_query sends user text to TTS."""
        ext = DeepTripExtension("test")
        ext.llm_client = None
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._handle_user_query(ten_env, "Hello")

        MockData.create.assert_called_once_with("tts_text_input")
        call_args = mock_output.set_property_from_json.call_args[0]
        payload = json.loads(call_args[1])
        assert payload["text"] == "Hello"
        assert payload["text_input_end"] is True
        ten_env.send_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_with_streaming_llm(self):
        """With a streaming LLM client, chunks are sent to TTS."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["This is ", "a great ", "place!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._handle_user_query(ten_env, "Tell me about this place")

        # Should call create for each chunk + final end marker
        ext.llm_client.chat.completions.create.assert_awaited_once()
        assert ten_env.send_data.await_count >= 2  # at least chunks + end marker

    @pytest.mark.asyncio
    async def test_query_with_location(self):
        """Location should be included in the system message to LLM."""
        ext = DeepTripExtension("test")
        ext.location = (35.6762, 139.6503)
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["Near Shibuya!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "What is nearby?")

        call_args = ext.llm_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages") if len(call_args) > 1 else None)
        system_content = messages[0]["content"]
        assert "35.6762,139.6503" in system_content

    @pytest.mark.asyncio
    async def test_query_with_search_results(self):
        """Search results should be included in the system message to LLM."""
        ext = DeepTripExtension("test")
        ext.location = (35.0, 139.0)
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[
            SearchResult(content="Senso-ji is a famous temple.", timestamp=1000),
            SearchResult(content="Built in 645 AD.", timestamp=1001),
        ])
        ext.client = mock_client
        ext.llm_client = make_streaming_llm(["Senso-ji is wonderful!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Tell me about Senso-ji")

        mock_client.search.assert_awaited_once()
        call_args = ext.llm_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages") if len(call_args) > 1 else None)
        system_content = messages[0]["content"]
        assert "Senso-ji is a famous temple." in system_content
        assert "Built in 645 AD." in system_content

    @pytest.mark.asyncio
    async def test_search_failure_graceful(self):
        """Search failure should not prevent LLM call and TTS output."""
        ext = DeepTripExtension("test")
        ext.location = (35.0, 139.0)
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("network error"))
        ext.client = mock_client
        ext.llm_client = make_streaming_llm(["I can still help!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Hello")

        ten_env.log_warn.assert_called()
        ext.llm_client.chat.completions.create.assert_awaited_once()
        assert ten_env.send_data.await_count >= 1

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self):
        """LLM failure should be handled gracefully."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"

        mock_llm = AsyncMock()
        mock_llm.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        ext.llm_client = mock_llm

        ten_env = make_ten_env()

        await ext._handle_user_query(ten_env, "Hello")

        ten_env.log_warn.assert_called()

    @pytest.mark.asyncio
    async def test_streaming_tts_chunk_format(self):
        """Streaming TTS chunks should use Data('tts_text_input') with JSON payload."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["Hello there!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_outputs = []
            def create_mock(name):
                m = MagicMock()
                mock_outputs.append(m)
                return m
            MockData.create.side_effect = create_mock
            await ext._handle_user_query(ten_env, "Hi")

        # Should have created Data objects (chunks + final end marker)
        assert len(mock_outputs) >= 2
        # All should be tts_text_input
        for call in MockData.create.call_args_list:
            assert call[0][0] == "tts_text_input"

        # Last output should be end marker
        last_payload = json.loads(mock_outputs[-1].set_property_from_json.call_args[0][1])
        assert last_payload["text_input_end"] is True
        assert last_payload["text"] == ""

    @pytest.mark.asyncio
    async def test_conversation_history_updated(self):
        """Conversation history should grow after successful streaming LLM call."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["Response ", "1"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Question 1")

        assert len(ext.conversation_history) == 2
        assert ext.conversation_history[0] == {"role": "user", "content": "Question 1"}
        assert ext.conversation_history[1] == {"role": "assistant", "content": "Response 1"}

    @pytest.mark.asyncio
    async def test_streaming_filters_thinking_blocks(self):
        """Thinking blocks should be filtered from streaming output."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["<think>", "reasoning", "</think>", "Clean output"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_outputs = []
            def create_mock(name):
                m = MagicMock()
                mock_outputs.append(m)
                return m
            MockData.create.side_effect = create_mock
            await ext._handle_user_query(ten_env, "Test")

        # Check conversation history has clean text
        assert ext.conversation_history[1]["content"] == "Clean output"

    @pytest.mark.asyncio
    async def test_stream_uses_stream_true(self):
        """LLM should be called with stream=True."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["Hello"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Hi")

        call_kwargs = ext.llm_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["stream"] is True


# ---------------------------------------------------------------------------
# _send_greeting
# ---------------------------------------------------------------------------

class TestSendGreeting:
    @pytest.mark.asyncio
    async def test_greeting_without_llm(self):
        """Without LLM client, sends static Japanese greeting."""
        ext = DeepTripExtension("test")
        ext.llm_client = None
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._send_greeting(ten_env)

        MockData.create.assert_called_once_with("tts_text_input")
        call_args = mock_output.set_property_from_json.call_args[0]
        payload = json.loads(call_args[1])
        assert "\u3053\u3093\u306b\u3061\u306f" in payload["text"]

    @pytest.mark.asyncio
    async def test_greeting_with_streaming_llm(self):
        """With LLM client, streams greeting via TTS chunks."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"
        ext.llm_client = make_streaming_llm(["Welcome ", "to Deep Trip!"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._send_greeting(ten_env)

        ext.llm_client.chat.completions.create.assert_awaited_once()
        assert ten_env.send_data.await_count >= 2  # chunks + end marker

    @pytest.mark.asyncio
    async def test_greeting_llm_failure_fallback(self):
        """LLM failure should send a static fallback greeting."""
        ext = DeepTripExtension("test")
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"

        mock_llm = AsyncMock()
        mock_llm.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
        ext.llm_client = mock_llm

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._send_greeting(ten_env)

        call_args = mock_output.set_property_from_json.call_args[0]
        payload = json.loads(call_args[1])
        assert "\u3053\u3093\u306b\u3061\u306f" in payload["text"]


# ---------------------------------------------------------------------------
# on_stop
# ---------------------------------------------------------------------------

class TestOnStop:
    @pytest.mark.asyncio
    async def test_stop_without_client(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        await ext.on_stop(ten_env)
        assert ext.client is None
        assert ext.llm_client is None

    @pytest.mark.asyncio
    async def test_stop_with_client(self):
        ext = DeepTripExtension("test")
        ext.client = MagicMock()
        ext.llm_client = MagicMock()
        ten_env = make_ten_env()

        await ext.on_stop(ten_env)

        # on_stop sets references to None; does NOT call stop()
        assert ext.client is None
        assert ext.llm_client is None


# ---------------------------------------------------------------------------
# Location state management
# ---------------------------------------------------------------------------

class TestLocationState:
    @pytest.mark.asyncio
    async def test_initial_location_is_none(self):
        ext = DeepTripExtension("test")
        assert ext.location is None

    @pytest.mark.asyncio
    async def test_location_updates_preserved(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()

        cmd1 = make_cmd("update_location", lat=35.0, lng=139.0)
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd1)
        assert ext.location == (35.0, 139.0)

        cmd2 = make_cmd("update_location", lat=34.0, lng=135.0)
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd2)
        assert ext.location == (34.0, 135.0)

    @pytest.mark.asyncio
    async def test_location_used_in_search(self):
        ext = DeepTripExtension("test")
        ext.location = (35.6762, 139.6503)
        ext.system_prompt = "You are Deep Trip."
        ext.llm_model = "gpt-4o-mini"

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])
        ext.client = mock_client
        ext.llm_client = make_streaming_llm(["response"])

        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "query")

        mock_client.search.assert_awaited_once()
        call_args = mock_client.search.call_args[0]
        assert call_args[1] == "35.6762,139.6503"


# ---------------------------------------------------------------------------
# _extract_non_thinking_text (streaming-aware)
# ---------------------------------------------------------------------------

class TestExtractNonThinkingText:
    def test_no_thinking(self):
        assert DeepTripExtension._extract_non_thinking_text("Hello world") == "Hello world"

    def test_complete_thinking_block(self):
        assert DeepTripExtension._extract_non_thinking_text(
            "<think>hmm</think>Hello"
        ) == "Hello"

    def test_multiline_thinking(self):
        text = "<think>\nline1\nline2\n</think>\nResult"
        assert DeepTripExtension._extract_non_thinking_text(text) == "Result"

    def test_unclosed_thinking_tag_truncated(self):
        """Unclosed <think> tag should be truncated (streaming partial)."""
        text = "Hello<think>partial reasoning"
        assert DeepTripExtension._extract_non_thinking_text(text) == "Hello"

    def test_empty_after_strip(self):
        assert DeepTripExtension._extract_non_thinking_text("<think>all</think>") == ""


# ---------------------------------------------------------------------------
# _strip_thinking (non-streaming)
# ---------------------------------------------------------------------------

class TestStripThinking:
    def test_no_thinking(self):
        assert DeepTripExtension._strip_thinking("Hello world") == "Hello world"

    def test_simple_thinking(self):
        assert DeepTripExtension._strip_thinking("<think>hmm</think>Hello") == "Hello"

    def test_multiline_thinking(self):
        text = "<think>\nline1\nline2\n</think>\nResult"
        assert DeepTripExtension._strip_thinking(text) == "Result"

    def test_empty_after_strip(self):
        assert DeepTripExtension._strip_thinking("<think>all thinking</think>") == ""
