import sys
from unittest.mock import MagicMock

# Stub ten_runtime before importing extension module
_ten_runtime_mock = MagicMock()
# Create real class stubs so DeepTripExtension can inherit from AsyncExtension
class _AsyncExtension:
    def __init__(self, name: str) -> None:
        self.name = name
_ten_runtime_mock.AsyncExtension = _AsyncExtension
_ten_runtime_mock.StatusCode.OK = 0
sys.modules.setdefault("ten_runtime", _ten_runtime_mock)

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

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
        return _props.get(key, "")

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
        return float(properties[key])

    cmd.get_property_float = MagicMock(side_effect=get_property_float)
    return cmd


def make_data(name, **properties):
    """Create a mock Data with given name and properties."""
    data = MagicMock()
    data.get_name = MagicMock(return_value=name)

    def get_property_bool(key):
        return bool(properties.get(key, False))

    def get_property_string(key):
        return str(properties.get(key, ""))

    data.get_property_bool = MagicMock(side_effect=get_property_bool)
    data.get_property_string = MagicMock(side_effect=get_property_string)
    return data


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

        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            mock_result = MagicMock()
            MockCmdResult.create.return_value = mock_result
            await ext.on_cmd(ten_env, cmd)

        ten_env.log_info.assert_any_call("User joined")
        ten_env.return_result.assert_awaited_once()

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
        # cmd that raises on get_property_float
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

        # Should still return result without error
        ten_env.return_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cmd_always_returns_result(self):
        """Every command should return a CmdResult regardless of cmd name."""
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()

        for cmd_name in ["on_user_joined", "on_user_left", "update_location", "anything"]:
            ten_env.return_result.reset_mock()
            cmd = make_cmd(cmd_name, lat=0.0, lng=0.0)
            with patch("deep_trip.extension.CmdResult") as MockCmdResult:
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
        data = make_data("asr_result", is_final=False, text="partial")

        await ext.on_data(ten_env, data)

        ten_env.send_data.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", is_final=True, text="")

        await ext.on_data(ten_env, data)

        ten_env.send_data.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_final_asr_sends_enriched_text(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        ten_env._props["SYSTEM_PROMPT"] = "You are Deep Trip."

        data = make_data("asr_result", is_final=True, text="Tell me about this place")

        # No client, no location
        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext.on_data(ten_env, data)

        MockData.create.assert_called_once_with("text_data")
        # Verify set_property_string was called with enriched text
        call_args = mock_output.set_property_string.call_args_list
        text_calls = [c for c in call_args if c[0][0] == "text"]
        assert len(text_calls) == 1
        enriched = text_calls[0][0][1]
        assert "You are Deep Trip." in enriched
        assert "Tell me about this place" in enriched
        ten_env.send_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_asr_with_location(self):
        ext = DeepTripExtension("test")
        ext.location = (35.6762, 139.6503)
        ten_env = make_ten_env()

        data = make_data("asr_result", is_final=True, text="What is nearby?")

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext.on_data(ten_env, data)

        text_calls = [c for c in mock_output.set_property_string.call_args_list
                      if c[0][0] == "text"]
        enriched = text_calls[0][0][1]
        assert "35.6762,139.6503" in enriched

    @pytest.mark.asyncio
    async def test_asr_with_search_results(self):
        ext = DeepTripExtension("test")
        ext.location = (35.0, 139.0)
        ten_env = make_ten_env()

        # Mock OpenClawClient
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[
            SearchResult(content="Senso-ji is a famous temple.", timestamp=1000),
            SearchResult(content="Built in 645 AD.", timestamp=1001),
        ])
        ext.client = mock_client

        data = make_data("asr_result", is_final=True, text="Tell me about Senso-ji")

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext.on_data(ten_env, data)

        text_calls = [c for c in mock_output.set_property_string.call_args_list
                      if c[0][0] == "text"]
        enriched = text_calls[0][0][1]
        assert "Senso-ji is a famous temple." in enriched
        assert "Built in 645 AD." in enriched
        assert "Context from Search" in enriched

    @pytest.mark.asyncio
    async def test_asr_search_failure_graceful(self):
        """Search failure should not prevent sending output."""
        ext = DeepTripExtension("test")
        ext.location = (35.0, 139.0)
        ten_env = make_ten_env()

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("network error"))
        ext.client = mock_client

        data = make_data("asr_result", is_final=True, text="Hello")

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext.on_data(ten_env, data)

        # Should still send data despite search failure
        ten_env.send_data.assert_awaited_once()
        ten_env.log_warn.assert_called()

    @pytest.mark.asyncio
    async def test_output_data_has_is_final_true(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        data = make_data("asr_result", is_final=True, text="Hi")

        with patch("deep_trip.extension.Data") as MockData:
            mock_output = MagicMock()
            MockData.create.return_value = mock_output
            await ext.on_data(ten_env, data)

        bool_calls = [c for c in mock_output.set_property_bool.call_args_list
                      if c[0][0] == "is_final"]
        assert len(bool_calls) == 1
        assert bool_calls[0][0][1] is True


# ---------------------------------------------------------------------------
# on_stop
# ---------------------------------------------------------------------------

class TestOnStop:
    @pytest.mark.asyncio
    async def test_stop_without_client(self):
        ext = DeepTripExtension("test")
        ten_env = make_ten_env()
        await ext.on_stop(ten_env)
        # Should not raise

    @pytest.mark.asyncio
    async def test_stop_with_client(self):
        ext = DeepTripExtension("test")
        mock_client = AsyncMock()
        mock_client.stop = AsyncMock()
        ext.client = mock_client
        ten_env = make_ten_env()

        await ext.on_stop(ten_env)

        mock_client.stop.assert_awaited_once()
        assert ext.client is None


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

        # First update
        cmd1 = make_cmd("update_location", lat=35.0, lng=139.0)
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd1)
        assert ext.location == (35.0, 139.0)

        # Second update overwrites
        cmd2 = make_cmd("update_location", lat=34.0, lng=135.0)
        with patch("deep_trip.extension.CmdResult") as MockCmdResult:
            MockCmdResult.create.return_value = MagicMock()
            await ext.on_cmd(ten_env, cmd2)
        assert ext.location == (34.0, 135.0)

    @pytest.mark.asyncio
    async def test_location_used_in_search(self):
        ext = DeepTripExtension("test")
        ext.location = (35.6762, 139.6503)
        ten_env = make_ten_env()

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])
        ext.client = mock_client

        data = make_data("asr_result", is_final=True, text="query")

        with patch("deep_trip.extension.Data") as MockData:
            MockData.create.return_value = MagicMock()
            await ext.on_data(ten_env, data)

        # Verify search was called with formatted location
        mock_client.search.assert_awaited_once()
        call_args = mock_client.search.call_args[0]
        assert call_args[1] == "35.6762,139.6503"
