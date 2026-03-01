#!/usr/bin/env python3
"""Pre-demo validation script for Deep Trip.

Checks that all required services and credentials are available before
starting the hackathon demo.

Usage:
    python demo/preflight_check.py
"""

import os
import subprocess
import sys

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(name: str, passed: bool, detail: str = "") -> None:
    global CHECKS_PASSED, CHECKS_FAILED
    if passed:
        CHECKS_PASSED += 1
        print(f"  PASS  {name}")
    else:
        CHECKS_FAILED += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    """Run a command and return (returncode, stdout)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip()
    except FileNotFoundError:
        return -1, "command not found"
    except subprocess.TimeoutExpired:
        return -1, "timed out"
    except Exception as e:
        return -1, str(e)


def main() -> None:
    print("=" * 50)
    print("  Deep Trip — Pre-Demo Preflight Check")
    print("=" * 50)
    print()

    # 1. Docker is running
    print("[Docker]")
    rc, out = run_cmd(["docker", "info"])
    check("Docker daemon running", rc == 0, "Start Docker Desktop" if rc != 0 else "")

    # 2. OpenClaw container is running
    rc, out = run_cmd(["docker", "ps", "--format", "{{.Names}}"])
    openclaw_running = "openclaw" in out.lower() if rc == 0 else False
    check(
        "OpenClaw container running",
        openclaw_running,
        "Run: docker compose up -d (in openclaw directory)" if not openclaw_running else "",
    )

    # 3. OpenClaw health check
    print()
    print("[OpenClaw]")
    container_name = os.getenv("OPENCLAW_HOST", "openclaw-test-openclaw-gateway-1")
    rc, out = run_cmd(
        ["docker", "exec", container_name, "npx", "openclaw", "health", "--json"],
        timeout=30,
    )
    check(
        "OpenClaw health check",
        rc == 0,
        f"Container '{container_name}' not responding" if rc != 0 else "",
    )

    # 4. MiniMax / OpenAI API reachable
    print()
    print("[LLM / MiniMax]")
    api_key = os.getenv("OPENAI_API_KEY", "")
    check(
        "OPENAI_API_KEY set",
        bool(api_key),
        "Set OPENAI_API_KEY in .env" if not api_key else "",
    )

    if api_key:
        # Quick connectivity test
        try:
            import urllib.request
            import json

            base_url = "https://api.minimax.io/v1"
            req = urllib.request.Request(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                check("MiniMax API reachable", resp.status == 200)
        except Exception as e:
            check("MiniMax API reachable", False, str(e))

    # 5. Agora credentials
    print()
    print("[Agora RTC]")
    agora_id = os.getenv("AGORA_APP_ID", "")
    check(
        "AGORA_APP_ID set",
        bool(agora_id),
        "Set AGORA_APP_ID in .env" if not agora_id else "",
    )

    agora_cert = os.getenv("AGORA_APP_CERTIFICATE", "")
    check(
        "AGORA_APP_CERTIFICATE set",
        bool(agora_cert),
        "Set AGORA_APP_CERTIFICATE in .env (optional for testing)" if not agora_cert else "",
    )

    # 6. Deepgram API key
    print()
    print("[Deepgram ASR]")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    check(
        "DEEPGRAM_API_KEY set",
        bool(deepgram_key),
        "Set DEEPGRAM_API_KEY in .env" if not deepgram_key else "",
    )

    # 7. MiniMax TTS keys
    print()
    print("[MiniMax TTS]")
    tts_key = os.getenv("MINIMAX_TTS_API_KEY", "")
    check(
        "MINIMAX_TTS_API_KEY set",
        bool(tts_key),
        "Set MINIMAX_TTS_API_KEY in .env" if not tts_key else "",
    )

    tts_group = os.getenv("MINIMAX_TTS_GROUP_ID", "")
    check(
        "MINIMAX_TTS_GROUP_ID set",
        bool(tts_group),
        "Set MINIMAX_TTS_GROUP_ID in .env" if not tts_group else "",
    )

    # Summary
    print()
    print("=" * 50)
    total = CHECKS_PASSED + CHECKS_FAILED
    print(f"  Results: {CHECKS_PASSED}/{total} passed, {CHECKS_FAILED} failed")
    if CHECKS_FAILED == 0:
        print("  All checks passed — ready for demo!")
    else:
        print("  Fix the failures above before starting the demo.")
    print("=" * 50)

    sys.exit(0 if CHECKS_FAILED == 0 else 1)


if __name__ == "__main__":
    main()
