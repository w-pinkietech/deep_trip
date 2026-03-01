import asyncio
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

CONTAINER_NAME = "openclaw-test-openclaw-gateway-1"


@dataclass
class OpenClawConfig:
    container_name: str = CONTAINER_NAME
    default_agent_id: str = "collab"
    default_channel: str = "whatsapp"
    agent_timeout_seconds: int = 600
    request_timeout_seconds: int = 180


@dataclass
class SearchResult:
    content: str
    timestamp: int


class SearchCache:
    """LRU cache with TTL for search results."""

    def __init__(self, maxsize: int = 50, ttl_seconds: int = 300) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> list | None:
        if key in self._cache:
            ts, results = self._cache[key]
            if time.time() - ts < self.ttl:
                self._cache.move_to_end(key)
                return results
            del self._cache[key]
        return None

    def put(self, key: str, results: list) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (time.time(), results)
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)


class OpenClawClient:
    """Executes OpenClaw CLI commands via docker exec against the gateway container."""

    def __init__(self, config: OpenClawConfig | None = None) -> None:
        self.config = config or OpenClawConfig()
        self._cache = SearchCache()

    async def _exec(self, *args: str, timeout: int | None = None) -> str:
        """Run `npx openclaw <args>` inside the gateway container and return stdout."""
        timeout = timeout or self.config.request_timeout_seconds
        cmd = [
            "docker", "exec", self.config.container_name,
            "npx", "openclaw", *args,
        ]
        logger.debug("exec: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"openclaw command timed out after {timeout}s")

        stdout_text = stdout.decode().strip() if stdout else ""
        stderr_text = stderr.decode().strip() if stderr else ""

        if proc.returncode != 0:
            raise RuntimeError(
                f"openclaw exited {proc.returncode}: {stderr_text or stdout_text}"
            )
        if stderr_text:
            logger.debug("stderr: %s", stderr_text)
        return stdout_text

    async def _exec_json(self, *args: str, timeout: int | None = None) -> Any:
        """Run a CLI command with --json and parse the JSON output."""
        raw = await self._exec(*args, "--json", timeout=timeout)
        return json.loads(raw)

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    async def agent(
        self,
        message: str,
        *,
        session_id: str | None = None,
        to: str | None = None,
        agent_id: str | None = None,
        deliver: bool = False,
        thinking: str | None = None,
    ) -> dict:
        """Run an agent turn via the gateway. Returns parsed JSON response."""
        resolved_agent = agent_id or self.config.default_agent_id
        args = ["agent", "--message", message]
        if session_id:
            args += ["--session-id", session_id]
        if to:
            args += ["--to", to]
        if resolved_agent:
            args += ["--agent", resolved_agent]
        if deliver:
            args.append("--deliver")
        if thinking:
            args += ["--thinking", thinking]
        return await self._exec_json(*args, timeout=self.config.agent_timeout_seconds)

    async def send_message(
        self,
        target: str,
        message: str,
        *,
        channel: str | None = None,
        media: str | None = None,
    ) -> dict:
        """Send a message via a chat channel."""
        ch = channel or self.config.default_channel
        args = [
            "message", "send",
            "--channel", ch,
            "--target", target,
            "--message", message,
        ]
        if media:
            args += ["--media", media]
        return await self._exec_json(*args)

    async def search(self, query: str, location: str) -> list[SearchResult]:
        """Send a search prompt to the agent and return results (with caching)."""
        cache_key = f"{query}|{location}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("cache hit: %s", cache_key)
            return cached

        prompt = f"Search for {query} near {location}"
        result = await self.agent(prompt)
        text = self.extract_text(result)
        ts = self.extract_timestamp(result) or int(time.time() * 1000)
        results = [SearchResult(content=text, timestamp=ts)]

        self._cache.put(cache_key, results)
        return results

    async def memory_search(
        self,
        query: str,
        *,
        agent_id: str | None = None,
        max_results: int | None = None,
    ) -> Any:
        """Search memory files."""
        args = ["memory", "search", query]
        if agent_id:
            args += ["--agent", agent_id]
        if max_results is not None:
            args += ["--max-results", str(max_results)]
        return await self._exec_json(*args)

    async def health(self) -> dict:
        """Fetch gateway health."""
        return await self._exec_json("health", timeout=10)

    async def devices_list(self) -> Any:
        """List paired devices."""
        return await self._exec_json("devices", "list")

    async def devices_approve(self, request_id: str | None = None) -> str:
        """Approve a device pairing request."""
        args = ["devices", "approve"]
        if request_id:
            args.append(request_id)
        else:
            args.append("--latest")
        return await self._exec(*args)

    # ------------------------------------------------------------------
    # Payload helpers (kept for compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_text(message: Any) -> str:
        if isinstance(message, str):
            return message.strip()
        if not isinstance(message, dict):
            return ""

        nested = message.get("message")
        nested_text = OpenClawClient.extract_text(nested)
        if nested_text:
            return nested_text

        content = message.get("content")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(
                    item.get("text"), str
                ):
                    texts.append(item["text"])
            if texts:
                return "\n".join(texts).strip()

        if isinstance(message.get("text"), str):
            return str(message.get("text", "")).strip()

        return ""

    @staticmethod
    def extract_timestamp(message: Any) -> int | None:
        if not isinstance(message, dict):
            return None
        ts = message.get("timestamp")
        if isinstance(ts, int):
            return ts
        if isinstance(ts, float):
            return int(ts)
        if isinstance(ts, str):
            try:
                normalized = ts.replace("Z", "+00:00")
                return int(
                    datetime.fromisoformat(normalized).timestamp() * 1000
                )
            except Exception:
                return None
        return None
