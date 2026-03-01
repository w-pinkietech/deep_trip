"""
Live integration test: connect to a real OpenClaw gateway and perform a search.

Prerequisites:
  - OpenClaw gateway running at ws://127.0.0.1:18789
  - Set OPENCLAW_GATEWAY_TOKEN env var if auth is required

Run:
  pytest deep_trip/tests/test_openclaw_live.py -v -s
"""

import asyncio
import logging
import os
import pytest
import pytest_asyncio
from deep_trip.openclaw_client import OpenClawClient, OpenClawConfig

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789")
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

pytestmark = pytest.mark.asyncio


async def _can_reach_gateway() -> bool:
    """Quick check: can we open a WebSocket to the gateway?"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(GATEWAY_URL, timeout=3) as ws:
                msg = await asyncio.wait_for(ws.receive(), timeout=3)
                await ws.close()
                return msg.type == aiohttp.WSMsgType.TEXT
    except Exception as e:
        logger.warning(f"Gateway not reachable: {e}")
        return False


@pytest_asyncio.fixture(scope="module")
async def client():
    config = OpenClawConfig(
        gateway_url=GATEWAY_URL,
        gateway_token=GATEWAY_TOKEN,
        gateway_device_identity_path="/tmp/deep_trip_test_device.json",
        request_timeout_ms=60000,
        connect_timeout_ms=10000,
    )
    c = OpenClawClient(config)

    reachable = await _can_reach_gateway()
    if not reachable:
        pytest.skip("OpenClaw gateway not reachable")

    await c.start()
    logger.info("Live client connected to gateway")
    yield c
    await c.stop()


# ---------------------------------------------------------------------------
# Live tests
# ---------------------------------------------------------------------------

async def test_gateway_connection(client: OpenClawClient):
    """Verify we can connect and complete the handshake."""
    assert client.ws is not None
    assert not client.ws.closed
    assert client._hello_event.is_set(), "Handshake should be completed"
    logger.info("Connection test PASSED")


async def test_send_chat(client: OpenClawClient):
    """Verify send_chat returns a task_id."""
    task_id = await client.send_chat("Hello, this is a connection test.")
    assert task_id, "send_chat should return a non-empty task_id"
    logger.info(f"send_chat returned task_id: {task_id}")


async def test_search_web(client: OpenClawClient):
    """The real test: can OpenClaw perform a web search and return results?"""
    query = "famous temples"
    location = "Asakusa, Tokyo"

    logger.info(f"Searching: '{query}' near '{location}'")

    results = await client.search(query, location)

    logger.info(f"Search returned {len(results)} result(s)")
    for i, r in enumerate(results):
        logger.info(f"  [{i}] content={r.content[:200]}...")
        logger.info(f"       timestamp={r.timestamp}")

    assert len(results) > 0, "Search should return at least one result"
    assert results[0].content, "Result content should not be empty"
    assert results[0].timestamp > 0, "Result should have a valid timestamp"

    content_lower = results[0].content.lower()
    logger.info(f"Full content:\n{results[0].content}")


async def test_search_location_context(client: OpenClawClient):
    """Search with specific GPS coordinates."""
    query = "historical landmarks"
    location = "35.7148,139.7967"  # Asakusa coordinates

    logger.info(f"Searching: '{query}' at GPS {location}")

    results = await client.search(query, location)

    logger.info(f"GPS search returned {len(results)} result(s)")
    for i, r in enumerate(results):
        logger.info(f"  [{i}] {r.content[:200]}...")

    assert len(results) > 0, "GPS-based search should return results"
    assert results[0].content, "Result content should not be empty"
