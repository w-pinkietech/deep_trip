#!/usr/bin/env python3
"""Verify MiniMax M2.5 via the OpenAI-compatible endpoint.

Usage:
    python scripts/verify_minimax.py

Requires OPENAI_API_KEY in .env (MiniMax API key).
"""

import asyncio
import os
import re
import sys
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

BASE_URL = "https://api.minimax.io/v1"
MODEL = "MiniMax-M2.5"
TEST_PROMPT = "日本で最も美しい隠れた名所を一つ教えてください。"


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def test_non_streaming(client: AsyncOpenAI) -> dict:
    """Test 1: Non-streaming chat completion."""
    print("\n--- Test 1: Non-streaming chat completion ---")
    start = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=300,
        )
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content or ""
        print(f"  Model:    {response.model}")
        print(f"  Content:  {content[:120]}...")
        print(f"  Time:     {elapsed:.2f}s")
        return {"pass": True, "time": elapsed, "content": content}
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"  FAILED:   {e}")
        return {"pass": False, "time": elapsed, "error": str(e)}


async def test_streaming(client: AsyncOpenAI) -> dict:
    """Test 2: Streaming chat completion with TTFB measurement."""
    print("\n--- Test 2: Streaming chat completion ---")
    start = time.perf_counter()
    ttfb = None
    chunks_received = 0
    content_parts: list[str] = []
    try:
        stream = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=300,
            stream=True,
        )
        async for chunk in stream:
            if ttfb is None:
                ttfb = time.perf_counter() - start
            chunks_received += 1
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                content_parts.append(delta.content)
        elapsed = time.perf_counter() - start
        full_content = "".join(content_parts)
        print(f"  Chunks:   {chunks_received}")
        print(f"  TTFB:     {ttfb:.2f}s" if ttfb else "  TTFB:     N/A")
        print(f"  Total:    {elapsed:.2f}s")
        print(f"  Content:  {full_content[:120]}...")
        return {"pass": True, "ttfb": ttfb, "time": elapsed, "content": full_content}
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"  FAILED:   {e}")
        return {"pass": False, "time": elapsed, "error": str(e)}


def test_strip_thinking(content: str) -> dict:
    """Test 3: Verify _strip_thinking works on model output."""
    print("\n--- Test 3: strip_thinking pattern ---")
    # Check if the raw content contains thinking tags
    has_thinking = bool(re.search(r"<think>", content))
    stripped = strip_thinking(content)
    still_has_thinking = bool(re.search(r"<think>", stripped))
    print(f"  Raw has <think> tags: {has_thinking}")
    print(f"  After strip:         {'clean' if not still_has_thinking else 'STILL HAS TAGS'}")
    print(f"  Stripped length:     {len(stripped)} chars")
    passed = not still_has_thinking and len(stripped) > 0
    return {"pass": passed, "had_thinking": has_thinking}


async def main() -> int:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        return 1

    print(f"MiniMax M2.5 Verification")
    print(f"Base URL: {BASE_URL}")
    print(f"Model:    {MODEL}")

    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)

    results: dict[str, dict] = {}

    # Test 1: Non-streaming
    results["non_streaming"] = await test_non_streaming(client)

    # Test 2: Streaming
    results["streaming"] = await test_streaming(client)

    # Test 3: strip_thinking on whichever content we have
    sample_content = ""
    for key in ("non_streaming", "streaming"):
        if results[key]["pass"] and results[key].get("content"):
            sample_content = results[key]["content"]
            break
    if sample_content:
        results["strip_thinking"] = test_strip_thinking(sample_content)
    else:
        print("\n--- Test 3: strip_thinking pattern ---")
        print("  SKIPPED (no content from previous tests)")
        results["strip_thinking"] = {"pass": False, "error": "no content"}

    # Summary
    print("\n=== Summary ===")
    all_pass = True
    for name, result in results.items():
        status = "PASS" if result["pass"] else "FAIL"
        timing = f" ({result['time']:.2f}s)" if "time" in result else ""
        print(f"  {name:20s} {status}{timing}")
        if not result["pass"]:
            all_pass = False

    if all_pass:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
