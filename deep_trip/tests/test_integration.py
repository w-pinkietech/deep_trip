"""
Integration tests for DeepTripExtension.

Tests the full pipeline: ASR input -> search -> streaming LLM -> TTS chunks,
with mocked external dependencies (LLM API, OpenClaw client).
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from deep_trip.extension import DeepTripExtension
from deep_trip.openclaw_client import SearchResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_ten_env():
    env = AsyncMock()
    env.log_debug = MagicMock()
    env.log_info = MagicMock()
    env.log_warn = MagicMock()
    env.log_error = MagicMock()
    _props = {}

    async def get_property_string(key):
        if key in _props:
            return (_props[key], None)
        raise Exception(f"Property {key} not found")

    env.get_property_string = AsyncMock(side_effect=get_property_string)
    env.return_result = AsyncMock()
    env.send_data = AsyncMock()
    env._props = _props
    return env


def make_cmd(name, **properties):
    cmd = MagicMock()
    cmd.get_name = MagicMock(return_value=name)

    def get_property_float(key):
        if key not in properties:
            raise ValueError(f"Property {key} not found")
        return (float(properties[key]), None)

    cmd.get_property_float = MagicMock(side_effect=get_property_float)
    return cmd


def make_data(name, **properties):
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


def make_extension_with_mocks(
    llm_chunks=None,
    search_results=None,
    system_prompt="You are Deep Trip, a Tokyo travel guide.",
):
    """Create a fully configured extension with mock streaming LLM and search client."""
    ext = DeepTripExtension("integration-test")
    ext.system_prompt = system_prompt
    ext.llm_model = "gpt-4o-mini"

    if llm_chunks is None:
        llm_chunks = ["Default ", "LLM ", "response."]
    ext.llm_client = make_streaming_llm(llm_chunks)

    mock_client = AsyncMock()
    if search_results is None:
        search_results = [SearchResult(content="Default search result.", timestamp=1000)]
    mock_client.search = AsyncMock(return_value=search_results)
    ext.client = mock_client

    return ext


def collect_tts_payloads(mock_outputs):
    """Extract JSON payloads from mock Data objects."""
    payloads = []
    for m in mock_outputs:
        if m.set_property_from_json.call_count > 0:
            raw = m.set_property_from_json.call_args[0][1]
            payloads.append(json.loads(raw))
    return payloads


# ---------------------------------------------------------------------------
# Full pipeline integration tests
# ---------------------------------------------------------------------------

class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_asr_to_tts_full_pipeline(self):
        """Test full pipeline: ASR data -> search -> streaming LLM -> TTS chunks."""
        ext = make_extension_with_mocks(
            llm_chunks=["Senso-ji ", "is a beautiful ", "temple in Asakusa."],
            search_results=[
                SearchResult(content="Senso-ji temple info", timestamp=1000),
            ],
        )
        ext.location = (35.7148, 139.7967)
        ten_env = make_ten_env()
        data = make_data("asr_result", final=True, text="Tell me about Senso-ji")

        with patch("deep_trip.extension.Data") as MockData:
            mock_outputs = []
            MockData.create.side_effect = lambda name: (
                mock_outputs.append(MagicMock()) or mock_outputs[-1]
            )
            await ext.on_data(ten_env, data)
            await asyncio.sleep(0.1)

        # Verify search was called with location
        ext.client.search.assert_awaited_once_with(
            "Tell me about Senso-ji", "35.7148,139.7967"
        )

        # Verify LLM was called with search context in messages
        ext.llm_client.chat.completions.create.assert_awaited_once()
        call_args = ext.llm_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Senso-ji temple info" in system_msg
        assert "35.7148,139.7967" in system_msg

        # Verify TTS chunks were sent
        payloads = collect_tts_payloads(mock_outputs)
        assert len(payloads) >= 2  # at least content + end marker
        # Last payload should be the end marker
        assert payloads[-1]["text_input_end"] is True

    @pytest.mark.asyncio
    async def test_pipeline_without_location(self):
        """Pipeline works without a GPS location set."""
        ext = make_extension_with_mocks(
            llm_chunks=["Welcome to Tokyo!"],
            search_results=[SearchResult(content="Tokyo info", timestamp=1000)],
        )
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Tell me about Tokyo")

        ext.client.search.assert_awaited_once_with("Tell me about Tokyo", "unknown location")

    @pytest.mark.asyncio
    async def test_pipeline_with_gps_coordinates(self):
        """Pipeline correctly formats GPS coordinates for search."""
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ext.location = (34.9677, 135.7726)
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "What's nearby?")

        ext.client.search.assert_awaited_once_with("What's nearby?", "34.9677,135.7726")


class TestSearchFailureHandling:
    @pytest.mark.asyncio
    async def test_search_failure_still_calls_llm(self):
        """When search fails, LLM should still be called without search context."""
        ext = make_extension_with_mocks(llm_chunks=["I can still help!"])
        ext.client.search = AsyncMock(side_effect=Exception("Search unavailable"))
        ext.location = (35.0, 139.0)
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Find a cafe")

        ten_env.log_warn.assert_called()
        ext.llm_client.chat.completions.create.assert_awaited_once()
        assert ten_env.send_data.await_count >= 1

    @pytest.mark.asyncio
    async def test_search_returns_empty(self):
        """Empty search results should still proceed to LLM call."""
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ext.client.search = AsyncMock(return_value=[])
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Hello")

        ext.llm_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_returns_empty_content(self):
        """Search results with empty content should be handled."""
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ext.client.search = AsyncMock(return_value=[
            SearchResult(content="", timestamp=1000),
        ])
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Hello")

        ext.llm_client.chat.completions.create.assert_awaited_once()


class TestLLMFailureHandling:
    @pytest.mark.asyncio
    async def test_llm_exception_handled(self):
        """LLM API exception should be caught and logged."""
        ext = make_extension_with_mocks()
        ext.llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limited")
        )
        ten_env = make_ten_env()

        await ext._handle_user_query(ten_env, "Hello")

        ten_env.log_warn.assert_called()

    @pytest.mark.asyncio
    async def test_no_llm_client_echoes_text(self):
        """Without LLM client, user text is echoed to TTS."""
        ext = make_extension_with_mocks()
        ext.llm_client = None
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._handle_user_query(ten_env, "Echo this")

        payload_str = mock_output.set_property_from_json.call_args[0][1]
        payload = json.loads(payload_str)
        assert payload["text"] == "Echo this"


class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_history_accumulates(self):
        """Conversation history should accumulate across multiple queries."""
        ext = make_extension_with_mocks(llm_chunks=["Response 1"])
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()

            await ext._handle_user_query(ten_env, "Question 1")
            assert len(ext.conversation_history) == 2

            # Second query
            ext.llm_client = make_streaming_llm(["Response 2"])
            await ext._handle_user_query(ten_env, "Question 2")
            assert len(ext.conversation_history) == 4

        assert ext.conversation_history[0] == {"role": "user", "content": "Question 1"}
        assert ext.conversation_history[1] == {"role": "assistant", "content": "Response 1"}
        assert ext.conversation_history[2] == {"role": "user", "content": "Question 2"}
        assert ext.conversation_history[3] == {"role": "assistant", "content": "Response 2"}

    @pytest.mark.asyncio
    async def test_history_included_in_llm_messages(self):
        """Previous conversation history should be sent to LLM."""
        ext = make_extension_with_mocks(llm_chunks=["First reply"])
        ext.system_prompt = "System prompt"
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()

            await ext._handle_user_query(ten_env, "First question")

            ext.llm_client = make_streaming_llm(["Second reply"])
            await ext._handle_user_query(ten_env, "Second question")

        # Check messages on second LLM call
        call_args = ext.llm_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert roles[0] == "system"
        assert roles[1] == "user"       # history
        assert roles[2] == "assistant"  # history
        assert roles[3] == "user"       # new question

    @pytest.mark.asyncio
    async def test_history_truncated_at_max(self):
        """Conversation history should be truncated at max_history."""
        ext = make_extension_with_mocks(llm_chunks=["Reply"])
        ext.max_history = 4
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()

            for i in range(5):
                ext.llm_client = make_streaming_llm([f"Reply {i}"])
                await ext._handle_user_query(ten_env, f"Question {i}")

        assert len(ext.conversation_history) == 4

    @pytest.mark.asyncio
    async def test_history_cleared_on_user_left(self):
        """on_user_left should clear conversation history."""
        ext = make_extension_with_mocks(llm_chunks=["Reply"])
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Build up history")

        assert len(ext.conversation_history) > 0

        cmd = make_cmd("on_user_left")
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        assert ext.conversation_history == []


class TestGreetingIntegration:
    @pytest.mark.asyncio
    async def test_greeting_on_user_joined(self):
        """on_user_joined should trigger a streaming greeting."""
        ext = make_extension_with_mocks(llm_chunks=["Welcome!"])
        ten_env = make_ten_env()
        cmd = make_cmd("on_user_joined")

        with patch("deep_trip.extension.CmdResult") as MockCmdResult, \
             patch("deep_trip.extension.Data") as MockData:
            MockCmdResult.create.return_value = MagicMock()
            MockData.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)
            await asyncio.sleep(0.1)

        ten_env.send_data.assert_awaited()

    @pytest.mark.asyncio
    async def test_greeting_fallback_without_llm(self):
        """Greeting without LLM should send a static Japanese greeting."""
        ext = DeepTripExtension("test")
        ext.llm_client = None
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext._send_greeting(ten_env)

        payload_str = mock_output.set_property_from_json.call_args[0][1]
        payload = json.loads(payload_str)
        assert "\u3053\u3093\u306b\u3061\u306f" in payload["text"]


class TestMultipleLocationTypes:
    @pytest.mark.asyncio
    async def test_tokyo_coordinates(self):
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ext.location = (35.6762, 139.6503)
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "What's here?")

        ext.client.search.assert_awaited_once_with("What's here?", "35.6762,139.6503")

    @pytest.mark.asyncio
    async def test_asakusa_coordinates(self):
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ext.location = (35.7148, 139.7967)
        ten_env = make_ten_env()

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "Nearby temples?")

        ext.client.search.assert_awaited_once_with("Nearby temples?", "35.7148,139.7967")

    @pytest.mark.asyncio
    async def test_location_update_via_cmd(self):
        """Location update via on_cmd integrates with search."""
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ten_env = make_ten_env()

        cmd = make_cmd("update_location", lat=35.6895, lng=139.6917)
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd)

        assert ext.location == (35.6895, 139.6917)

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext._handle_user_query(ten_env, "What's here?")

        ext.client.search.assert_awaited_once_with("What's here?", "35.6895,139.6917")

    @pytest.mark.asyncio
    async def test_location_update_via_data_channel(self):
        """Location update via data_in channel."""
        ext = make_extension_with_mocks(llm_chunks=["Response"])
        ten_env = make_ten_env()

        payload = json.dumps({"cmd": "update_location", "lat": 35.6580, "lng": 139.7016})
        data = make_data("data_in", data=payload)
        await ext.on_data(ten_env, data)

        assert ext.location == (35.6580, 139.7016)
