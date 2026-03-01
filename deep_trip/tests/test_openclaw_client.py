import pytest
import asyncio
import json
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from deep_trip.openclaw_client import OpenClawClient, OpenClawConfig, SearchResult, DeviceIdentity
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.send_str = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws

@pytest.fixture
def client(mock_ws):
    config = OpenClawConfig(
        gateway_url="ws://test",
        gateway_token="test_token",
        gateway_device_identity_path="/tmp/test_identity.json",
        request_timeout_ms=1000  # Short timeout for tests
    )
    client = OpenClawClient(config)
    client.session = AsyncMock()
    client.session.ws_connect = AsyncMock(return_value=mock_ws)
    
    # Mock device identity
    priv = Ed25519PrivateKey.generate()
    client._device_identity = DeviceIdentity("test_device", "pubkey", priv)
    
    return client

@pytest.mark.asyncio
async def test_search_success(client, mock_ws):
    # Mock connection established
    client.ws = mock_ws
    client._hello_event.set()
    
    # Mock send_chat response (returns task_id)
    # search calls send_chat which calls _request
    # We can mock _request to avoid mocking the whole protocol for send_chat
    # But we want to test search waiting logic.
    
    # Mock _request to return "OK" for chat.send
    client._request = AsyncMock(return_value={"status": "ok"})
    
    # Simulate incoming chat response
    async def simulate_response():
        await asyncio.sleep(0.1)
        # Manually trigger message handling
        payload = {
            "state": "final",
            "message": {
                "text": "Found it!"
            },
            "timestamp": 1234567890000
        }
        await client._handle_message(json.dumps({
            "type": "event",
            "event": "chat",
            "payload": payload
        }))

    # Start simulation
    asyncio.create_task(simulate_response())
    
    # Run search
    results = await client.search("query", "location")
    
    assert len(results) == 1
    assert results[0].content == "Found it!"
    assert results[0].timestamp == 1234567890000

@pytest.mark.asyncio
async def test_search_timeout(client, mock_ws):
    client.ws = mock_ws
    client._hello_event.set()
    client._request = AsyncMock(return_value={"status": "ok"})
    
    # No response simulation
    
    with pytest.raises(TimeoutError):
        await client.search("query", "location")

@pytest.mark.asyncio
async def test_connect_handshake(client, mock_ws):
    # Setup mock_ws on client
    client.ws = mock_ws
    
    # We want to test that _send_connect is called and sends correct frame
    
    # Setup nonce for challenge
    nonce = "test_nonce"
    
    # Mock _recv_loop behavior? 
    # Or just call _handle_message with connect.challenge
    
    # We need to spy on ws.send_str
    
    # Call _handle_message with challenge
    challenge = {
        "type": "event",
        "event": "connect.challenge",
        "payload": {"nonce": nonce}
    }
    
    # This should trigger _send_connect_background
    await client._handle_message(json.dumps(challenge))
    
    # Wait a bit for background task
    await asyncio.sleep(0.1)
    
    # Verify send_str was called with connect request
    assert mock_ws.send_str.called
    call_args = mock_ws.send_str.call_args[0][0]
    frame = json.loads(call_args)
    assert frame["method"] == "connect"
    assert frame["params"]["device"]["nonce"] == nonce
