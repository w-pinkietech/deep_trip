import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Coroutine, Optional, Callable

import aiohttp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

DEFAULT_CLIENT_ID = "deep-trip-client"
DEFAULT_CLIENT_MODE = "backend"

@dataclass
class OpenClawConfig:
    gateway_url: str = "ws://127.0.0.1:18789"
    gateway_token: str = ""
    gateway_password: str = ""
    gateway_scopes: str = "operator.write"
    gateway_client_id: str = DEFAULT_CLIENT_ID
    gateway_client_mode: str = DEFAULT_CLIENT_MODE
    gateway_origin: str = ""
    gateway_device_identity_path: str = "~/.openclaw/identity/deep_trip_device.json"
    chat_session_key: str = "agent:deep_trip:main"
    request_timeout_ms: int = 180000
    connect_timeout_ms: int = 10000

@dataclass
class DeviceIdentity:
    device_id: str
    public_key_raw_b64url: str
    private_key: Ed25519PrivateKey

class GatewayRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

class OpenClawClient:
    def __init__(self, config: OpenClawConfig) -> None:
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.recv_task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()
        self._hello_event = asyncio.Event()
        self._response_waiters: dict[str, asyncio.Future] = {}
        self._connect_sent = False
        self._connect_nonce = ""
        self._stopped = False
        self._device_identity: DeviceIdentity | None = None
        self._background_tasks: set[asyncio.Task] = set()
        
        # Callbacks
        self.on_chat_message: Callable[[dict], Coroutine[Any, Any, None]] | None = None
        self.on_pairing_required: Callable[[dict], Coroutine[Any, Any, None]] | None = None

    async def start(self) -> None:
        self._device_identity = self._load_or_create_device_identity()
        self.session = aiohttp.ClientSession()
        await self._ensure_connected()
        logger.info("OpenClaw client connected and ready.")

    async def stop(self) -> None:
        self._stopped = True
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        if self.recv_task:
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
            self.recv_task = None
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        if self.session is not None:
            await self.session.close()
            self.session = None
        self._hello_event.clear()
        for fut in self._response_waiters.values():
            if not fut.done():
                fut.set_exception(RuntimeError("client stopped"))
        self._response_waiters.clear()

    async def send_chat(self, message: str) -> str:
        """Sends a chat message to OpenClaw. Returns task_id."""
        task_id = str(uuid.uuid4())
        await self._ensure_connected()
        await self._request(
            "chat.send",
            {
                "sessionKey": self.config.chat_session_key,
                "message": message,
                "deliver": False,
                "idempotencyKey": task_id,
            },
            timeout_ms=self.config.request_timeout_ms,
        )
        return task_id

    async def _ensure_connected(self) -> None:
        async with self._connect_lock:
            if self._stopped:
                raise RuntimeError("client stopped")
            if self.ws is None or self.ws.closed:
                await self._open_connection()
            timeout_s = max(self.config.connect_timeout_ms, 1000) / 1000
            deadline = time.monotonic() + timeout_s
            while not self._hello_event.is_set():
                if self.ws is None or self.ws.closed:
                    raise RuntimeError(self._describe_ws_state())
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        f"connect handshake timeout after {int(timeout_s * 1000)}ms; {self._describe_ws_state()}"
                    )
                try:
                    await asyncio.wait_for(
                        self._hello_event.wait(),
                        timeout=min(0.2, remaining),
                    )
                except asyncio.TimeoutError:
                    continue

    async def _open_connection(self) -> None:
        if self.session is None:
            raise RuntimeError("http session not initialized")
        self._hello_event.clear()
        self._connect_sent = False
        self._connect_nonce = ""
        headers: dict[str, str] = {}
        origin = str(self.config.gateway_origin or "").strip()
        if origin:
            headers["Origin"] = origin
        try:
            self.ws = await self.session.ws_connect(
                self.config.gateway_url,
                headers=headers if headers else None,
            )
            self.recv_task = asyncio.create_task(self._recv_loop())
        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            raise

    async def _recv_loop(self) -> None:
        assert self.ws is not None
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                await self._handle_message(str(msg.data))
        except Exception as exc:
            logger.warning(
                f"OpenClaw receive loop ended with error: {self._describe_connect_error(exc)}"
            )
        finally:
            logger.info(
                f"OpenClaw receive loop closed: {self._describe_ws_state()}"
            )
            self._hello_event.clear()
            if self.ws is not None and not self.ws.closed:
                await self.ws.close()
            self.ws = None

    async def _handle_message(self, raw: str) -> None:
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            return

        frame_type = frame.get("type")
        if frame_type == "event":
            event_name = frame.get("event")
            payload = frame.get("payload")
            if event_name == "connect.challenge":
                self._connect_nonce = self._extract_connect_nonce(payload)
                self._create_background_task(self._send_connect_background())
                return
            if event_name == "chat":
                if self.on_chat_message:
                    await self.on_chat_message(payload)
                return

        if frame_type == "res":
            req_id = str(frame.get("id", ""))
            fut = self._response_waiters.pop(req_id, None)
            if fut is None or fut.done():
                return
            if frame.get("ok"):
                fut.set_result(frame.get("payload"))
            else:
                error = frame.get("error", {}) or {}
                message = str(error.get("message", "request failed"))
                code = str(error.get("code", ""))
                details = (
                    error.get("details")
                    if isinstance(error.get("details"), dict)
                    else {}
                )
                fut.set_exception(
                    GatewayRequestError(
                        message,
                        code=code,
                        details=details,
                    )
                )

        if frame_type == "hello-ok":
            self._hello_event.set()

    async def _send_connect_background(self) -> None:
        try:
            await self._send_connect()
        except Exception as exc:
            logger.warning(
                f"connect request failed: {self._describe_connect_error(exc)}"
            )
            if self.on_pairing_required:
                payload = self._build_pairing_required_payload(exc)
                if payload:
                    await self.on_pairing_required(payload)

    def _create_background_task(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _send_connect(self) -> None:
        if self._connect_sent:
            return
        nonce = self._connect_nonce.strip()
        if not nonce:
            raise RuntimeError("gateway connect challenge missing nonce")
        self._connect_sent = True
        scopes = [
            s.strip()
            for s in str(self.config.gateway_scopes or "").split(",")
            if s.strip()
        ]
        client_id = str(self.config.gateway_client_id or "").strip()
        client_mode = str(self.config.gateway_client_mode or "").strip()

        logger.info(
            f"connect with client.id={client_id}, client.mode={client_mode}"
        )

        auth_token = str(self.config.gateway_token or "").strip()
        auth_password = str(self.config.gateway_password or "").strip()
        signed_at_ms = int(time.time() * 1000)
        payload = {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": client_id,
                "version": "0.1.0",
                "platform": "python-client",
                "mode": client_mode,
            },
            "role": "operator",
            "scopes": scopes,
            "caps": [],
            "locale": "en-US",
            "device": self._build_device_payload(
                client_id=client_id,
                client_mode=client_mode,
                scopes=scopes,
                signed_at_ms=signed_at_ms,
                token=auth_token,
                nonce=nonce,
            ),
        }
        if auth_token:
            payload["auth"] = {"token": auth_token}
        elif auth_password:
            payload["auth"] = {"password": auth_password}

        hello = await self._request(
            method="connect",
            params=payload,
            timeout_ms=self.config.connect_timeout_ms,
        )
        if isinstance(hello, dict) and hello.get("type") == "hello-ok":
            self._hello_event.set()

    async def _request(self, method: str, params: Any, timeout_ms: int) -> Any:
        if self.ws is None or self.ws.closed:
            raise RuntimeError("gateway not connected")

        req_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._response_waiters[req_id] = fut

        frame = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params,
        }
        await self.ws.send_str(json.dumps(frame))

        timeout = max(timeout_ms, 1000) / 1000
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._response_waiters.pop(req_id, None)

    def _load_or_create_device_identity(self) -> DeviceIdentity:
        identity_path = Path(
            os.path.expanduser(
                str(self.config.gateway_device_identity_path or "").strip()
                or "~/.openclaw/identity/deep_trip_device.json"
            )
        )
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        if identity_path.exists():
            loaded = self._load_device_identity(identity_path)
            if loaded:
                return loaded
            logger.warning(
                "invalid device identity file, regenerating"
            )

        private_key = Ed25519PrivateKey.generate()
        public_key_raw = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        device_id = hashlib.sha256(public_key_raw).hexdigest()
        public_key_pem = (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        payload = {
            "version": 1,
            "device_id": device_id,
            "public_key_pem": public_key_pem,
            "private_key_pem": private_key_pem,
            "created_at_ms": int(time.time() * 1000),
        }
        identity_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(identity_path, 0o600)
        except OSError:
            pass

        return DeviceIdentity(
            device_id=device_id,
            public_key_raw_b64url=self._base64url_encode(public_key_raw),
            private_key=private_key,
        )

    def _load_device_identity(
        self, identity_path: Path
    ) -> DeviceIdentity | None:
        try:
            payload = json.loads(identity_path.read_text(encoding="utf-8"))
            private_key_pem = str(payload.get("private_key_pem", "")).strip()
            public_key_pem = str(payload.get("public_key_pem", "")).strip()
            if not private_key_pem or not public_key_pem:
                return None

            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )
            if not isinstance(private_key, Ed25519PrivateKey):
                return None
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode()
            )
            if not isinstance(public_key, Ed25519PublicKey):
                return None

            public_key_raw = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            device_id = hashlib.sha256(public_key_raw).hexdigest()
            return DeviceIdentity(
                device_id=device_id,
                public_key_raw_b64url=self._base64url_encode(public_key_raw),
                private_key=private_key,
            )
        except Exception as exc:
            logger.warning(f"failed to load device identity: {exc}")
            return None

    def _build_device_payload(
        self,
        *,
        client_id: str,
        client_mode: str,
        scopes: list[str],
        signed_at_ms: int,
        token: str,
        nonce: str,
    ) -> dict[str, Any]:
        if self._device_identity is None:
            raise RuntimeError("device identity not initialized")
        device = self._device_identity
        signature_payload = self._build_device_auth_payload(
            device_id=device.device_id,
            client_id=client_id,
            client_mode=client_mode,
            role="operator",
            scopes=scopes,
            signed_at_ms=signed_at_ms,
            token=token,
            nonce=nonce,
        )
        signature = device.private_key.sign(signature_payload.encode("utf-8"))
        return {
            "id": device.device_id,
            "publicKey": device.public_key_raw_b64url,
            "signature": self._base64url_encode(signature),
            "signedAt": signed_at_ms,
            "nonce": nonce,
        }

    @staticmethod
    def _build_device_auth_payload(
        *,
        device_id: str,
        client_id: str,
        client_mode: str,
        role: str,
        scopes: list[str],
        signed_at_ms: int,
        token: str,
        nonce: str,
    ) -> str:
        return "|".join(
            [
                "v2",
                device_id,
                client_id,
                client_mode,
                role,
                ",".join(scopes),
                str(signed_at_ms),
                token or "",
                nonce,
            ]
        )

    @staticmethod
    def _extract_connect_nonce(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        nonce = payload.get("nonce")
        return str(nonce).strip() if isinstance(nonce, str) else ""

    @staticmethod
    def _base64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

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

    def _describe_connect_error(self, exc: Exception) -> str:
        raw = str(exc).strip()
        if raw:
            return raw
        return f"{exc.__class__.__name__}; {self._describe_ws_state()}"

    def _describe_ws_state(self) -> str:
        if self.ws is None:
            return "ws_state=none"
        close_code = getattr(self.ws, "close_code", None)
        ws_exc = self.ws.exception()
        ws_exc_text = str(ws_exc).strip() if ws_exc else ""
        return (
            f"ws_state=closed:{bool(self.ws.closed)} "
            f"close_code={close_code} "
            f"nonce_received={bool(self._connect_nonce)} "
            f"ws_exception={ws_exc_text or 'none'}"
        )

    def _build_pairing_required_payload(
        self, exc: Exception
    ) -> dict[str, Any] | None:
        message = self._describe_connect_error(exc)
        details: dict[str, Any] = {}
        code = ""
        if isinstance(exc, GatewayRequestError):
            details = exc.details
            code = str(exc.code or "").strip().lower()
        message_lower = message.lower()
        is_pairing_required = (
            "pairing required" in message_lower
            or "missing scope: operator.write" in message_lower
            or code == "pairing_required"
        )
        if not is_pairing_required:
            return None
        request_id = str(details.get("requestId", "")).strip()
        approve_cmd = (
            f"openclaw devices approve {request_id}"
            if request_id
            else "openclaw devices approve --latest"
        )
        return {
            "pairing_required": True,
            "pairing_list_cmd": "openclaw devices list",
            "pairing_approve_cmd": approve_cmd,
            "pairing_hint": "Run these commands on the gateway host, then restart this agent.",
        }
