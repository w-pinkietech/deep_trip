import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
from deep_trip.openclaw_client import (
    OpenClawClient,
    OpenClawConfig,
    SearchResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return OpenClawConfig(
        container_name="test-container",
        request_timeout_seconds=5,
        agent_timeout_seconds=10,
    )


@pytest.fixture
def client(config):
    return OpenClawClient(config)


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_plain_string(self):
        assert OpenClawClient.extract_text("hello world") == "hello world"

    def test_string_with_whitespace(self):
        assert OpenClawClient.extract_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert OpenClawClient.extract_text("") == ""

    def test_none_returns_empty(self):
        assert OpenClawClient.extract_text(None) == ""

    def test_int_returns_empty(self):
        assert OpenClawClient.extract_text(42) == ""

    def test_nested_message_text(self):
        payload = {"message": {"text": "nested text"}}
        assert OpenClawClient.extract_text(payload) == "nested text"

    def test_content_string(self):
        payload = {"content": "content string"}
        assert OpenClawClient.extract_text(payload) == "content string"

    def test_content_list(self):
        payload = {
            "content": [
                {"type": "text", "text": "line1"},
                {"type": "text", "text": "line2"},
            ]
        }
        assert OpenClawClient.extract_text(payload) == "line1\nline2"

    def test_content_list_skips_non_text(self):
        payload = {
            "content": [
                {"type": "image", "url": "http://img"},
                {"type": "text", "text": "only text"},
            ]
        }
        assert OpenClawClient.extract_text(payload) == "only text"

    def test_content_list_skips_non_dict(self):
        payload = {"content": ["raw", {"type": "text", "text": "ok"}]}
        assert OpenClawClient.extract_text(payload) == "ok"

    def test_top_level_text_key(self):
        payload = {"text": "top level"}
        assert OpenClawClient.extract_text(payload) == "top level"

    def test_nested_message_takes_priority(self):
        payload = {"message": {"text": "inner"}, "text": "outer"}
        assert OpenClawClient.extract_text(payload) == "inner"

    def test_empty_dict(self):
        assert OpenClawClient.extract_text({}) == ""

    def test_deeply_nested(self):
        payload = {"message": {"message": {"text": "deep"}}}
        assert OpenClawClient.extract_text(payload) == "deep"


# ---------------------------------------------------------------------------
# extract_timestamp
# ---------------------------------------------------------------------------

class TestExtractTimestamp:
    def test_int_timestamp(self):
        assert OpenClawClient.extract_timestamp({"timestamp": 1234567890000}) == 1234567890000

    def test_float_timestamp(self):
        assert OpenClawClient.extract_timestamp({"timestamp": 1234567890.5}) == 1234567890

    def test_iso_string_timestamp(self):
        ts = OpenClawClient.extract_timestamp({"timestamp": "2024-01-01T00:00:00Z"})
        assert ts is not None
        assert ts > 0

    def test_iso_string_with_offset(self):
        ts = OpenClawClient.extract_timestamp({"timestamp": "2024-01-01T09:00:00+09:00"})
        assert ts is not None
        assert ts > 0

    def test_invalid_string_returns_none(self):
        assert OpenClawClient.extract_timestamp({"timestamp": "not-a-date"}) is None

    def test_missing_timestamp(self):
        assert OpenClawClient.extract_timestamp({}) is None

    def test_none_input(self):
        assert OpenClawClient.extract_timestamp(None) is None

    def test_non_dict_input(self):
        assert OpenClawClient.extract_timestamp("string") is None
        assert OpenClawClient.extract_timestamp(42) is None


# ---------------------------------------------------------------------------
# _exec
# ---------------------------------------------------------------------------

def _make_mock_process(stdout=b"", stderr=b"", returncode=0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


class TestExec:
    @pytest.mark.asyncio
    async def test_successful_exec(self, client):
        mock_proc = _make_mock_process(stdout=b"OK\n")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await client._exec("health")
            assert result == "OK"
            mock_create.assert_called_once_with(
                "docker", "exec", "test-container",
                "npx", "openclaw", "health",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_nonzero_exit_raises(self, client):
        mock_proc = _make_mock_process(stderr=b"error msg", returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="error msg"):
                await client._exec("bad-cmd")

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, client):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.kill = MagicMock()
        proc.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(TimeoutError, match="timed out"):
                await client._exec("slow-cmd", timeout=1)
            proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# _exec_json
# ---------------------------------------------------------------------------

class TestExecJson:
    @pytest.mark.asyncio
    async def test_parses_json_output(self, client):
        data = {"status": "ok", "count": 3}
        mock_proc = _make_mock_process(stdout=json.dumps(data).encode())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client._exec_json("health")
            assert result == data

    @pytest.mark.asyncio
    async def test_appends_json_flag(self, client):
        mock_proc = _make_mock_process(stdout=b'{"ok":true}')
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client._exec_json("health")
            args = mock_create.call_args[0]
            assert args[-1] == "--json"


# ---------------------------------------------------------------------------
# agent
# ---------------------------------------------------------------------------

class TestAgent:
    @pytest.mark.asyncio
    async def test_basic_agent_call(self, client):
        response = {"text": "result"}
        mock_proc = _make_mock_process(stdout=json.dumps(response).encode())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await client.agent("hello")
            assert result == response
            args = mock_create.call_args[0]
            assert "agent" in args
            assert "--message" in args
            assert "hello" in args

    @pytest.mark.asyncio
    async def test_agent_with_options(self, client):
        mock_proc = _make_mock_process(stdout=b'{}')
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client.agent(
                "test", session_id="s1", to="+1234", agent_id="ops",
                deliver=True, thinking="high",
            )
            args = mock_create.call_args[0]
            assert "--session-id" in args
            assert "s1" in args
            assert "--to" in args
            assert "+1234" in args
            assert "--agent" in args
            assert "ops" in args
            assert "--deliver" in args
            assert "--thinking" in args
            assert "high" in args


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message(self, client):
        mock_proc = _make_mock_process(stdout=b'{"id":"msg1"}')
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await client.send_message("+1234", "hi")
            assert result == {"id": "msg1"}
            args = mock_create.call_args[0]
            assert "message" in args
            assert "send" in args
            assert "--target" in args
            assert "+1234" in args
            assert "--message" in args
            assert "hi" in args

    @pytest.mark.asyncio
    async def test_send_message_with_media(self, client):
        mock_proc = _make_mock_process(stdout=b'{}')
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client.send_message("+1234", "photo", media="/tmp/img.jpg")
            args = mock_create.call_args[0]
            assert "--media" in args
            assert "/tmp/img.jpg" in args


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, client):
        response = {"message": {"text": "Found cafe nearby"}, "timestamp": 1234567890000}
        mock_proc = _make_mock_process(stdout=json.dumps(response).encode())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            results = await client.search("cafe", "Tokyo")
            assert len(results) == 1
            assert results[0].content == "Found cafe nearby"
            assert results[0].timestamp == 1234567890000

    @pytest.mark.asyncio
    async def test_search_timeout(self, client):
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.kill = MagicMock()
        proc.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(TimeoutError):
                await client.search("query", "location")


# ---------------------------------------------------------------------------
# memory_search
# ---------------------------------------------------------------------------

class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_memory_search(self, client):
        data = [{"text": "note", "score": 0.9}]
        mock_proc = _make_mock_process(stdout=json.dumps(data).encode())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await client.memory_search("deployment")
            assert result == data
            args = mock_create.call_args[0]
            assert "memory" in args
            assert "search" in args
            assert "deployment" in args

    @pytest.mark.asyncio
    async def test_memory_search_with_options(self, client):
        mock_proc = _make_mock_process(stdout=b'[]')
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client.memory_search("q", agent_id="ops", max_results=5)
            args = mock_create.call_args[0]
            assert "--agent" in args
            assert "ops" in args
            assert "--max-results" in args
            assert "5" in args


# ---------------------------------------------------------------------------
# health / devices
# ---------------------------------------------------------------------------

class TestHealthAndDevices:
    @pytest.mark.asyncio
    async def test_health(self, client):
        data = {"status": "ok"}
        mock_proc = _make_mock_process(stdout=json.dumps(data).encode())
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.health()
            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_devices_approve_with_id(self, client):
        mock_proc = _make_mock_process(stdout=b"approved")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            result = await client.devices_approve("req-123")
            assert result == "approved"
            args = mock_create.call_args[0]
            assert "req-123" in args

    @pytest.mark.asyncio
    async def test_devices_approve_latest(self, client):
        mock_proc = _make_mock_process(stdout=b"approved")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await client.devices_approve()
            args = mock_create.call_args[0]
            assert "--latest" in args
