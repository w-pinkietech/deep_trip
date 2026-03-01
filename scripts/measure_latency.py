#!/usr/bin/env python3
"""Measure component latencies for the Deep Trip pipeline.

Standalone script that benchmarks:
  1. OpenClaw search latency
  2. LLM time-to-first-byte (TTFB) and total generation time
  3. End-to-end pipeline latency

Usage:
    python scripts/measure_latency.py
    python scripts/measure_latency.py --query "sensoji temple history" --location "35.7148,139.7967"
    python scripts/measure_latency.py --runs 5
"""
import argparse
import asyncio
import os
import sys
import time

from openai import AsyncOpenAI

# Allow importing from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deep_trip.openclaw_client import OpenClawClient, OpenClawConfig


async def measure_search(client: OpenClawClient, query: str, location: str) -> float:
    """Measure search latency in ms."""
    t0 = time.monotonic()
    try:
        results = await client.search(query, location)
        elapsed = (time.monotonic() - t0) * 1000
        content_len = sum(len(r.content) for r in results) if results else 0
        print(f"  Search: {elapsed:.0f}ms ({content_len} chars)")
        return elapsed
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        print(f"  Search: FAILED after {elapsed:.0f}ms — {e}")
        return elapsed


async def measure_llm(
    llm_client: AsyncOpenAI, model: str, query: str, context: str = ""
) -> tuple[float, float]:
    """Measure LLM TTFB and total time in ms. Returns (ttfb, total)."""
    messages = []
    if context:
        messages.append({"role": "system", "content": f"Context:\n{context}"})
    messages.append({"role": "user", "content": query})

    t0 = time.monotonic()
    ttfb = 0.0
    total_tokens = 0
    try:
        stream = await llm_client.chat.completions.create(
            model=model, messages=messages, max_tokens=500, stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content or ""
            if content and ttfb == 0:
                ttfb = (time.monotonic() - t0) * 1000
            total_tokens += len(content)

        total = (time.monotonic() - t0) * 1000
        print(f"  LLM TTFB: {ttfb:.0f}ms | Total: {total:.0f}ms | Chars: {total_tokens}")
        return ttfb, total
    except Exception as e:
        total = (time.monotonic() - t0) * 1000
        print(f"  LLM: FAILED after {total:.0f}ms — {e}")
        return total, total


async def run_benchmark(query: str, location: str, runs: int) -> None:
    # Setup clients
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1")
    model = os.environ.get("LLM_MODEL", "MiniMax-M2.5")
    container = os.environ.get("OPENCLAW_HOST", "openclaw-test-openclaw-gateway-1")

    config = OpenClawConfig(container_name=container)
    search_client = OpenClawClient(config)

    llm_client = None
    if api_key:
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        llm_client = AsyncOpenAI(**kwargs)

    print(f"Query: {query}")
    print(f"Location: {location}")
    print(f"LLM model: {model}")
    print(f"Runs: {runs}")
    print("=" * 50)

    search_times = []
    ttfb_times = []
    total_times = []

    for i in range(runs):
        print(f"\n--- Run {i + 1}/{runs} ---")
        t_pipeline = time.monotonic()

        # 1. Search
        s = await measure_search(search_client, query, location)
        search_times.append(s)

        # 2. LLM (if configured)
        if llm_client:
            ttfb, total = await measure_llm(llm_client, model, query)
            ttfb_times.append(ttfb)
            total_times.append(total)

        pipeline_ms = (time.monotonic() - t_pipeline) * 1000
        print(f"  Pipeline: {pipeline_ms:.0f}ms")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    if search_times:
        avg_search = sum(search_times) / len(search_times)
        print(f"Search avg: {avg_search:.0f}ms (min={min(search_times):.0f}, max={max(search_times):.0f})")
    if ttfb_times:
        avg_ttfb = sum(ttfb_times) / len(ttfb_times)
        print(f"LLM TTFB avg: {avg_ttfb:.0f}ms (min={min(ttfb_times):.0f}, max={max(ttfb_times):.0f})")
    if total_times:
        avg_total = sum(total_times) / len(total_times)
        print(f"LLM Total avg: {avg_total:.0f}ms (min={min(total_times):.0f}, max={max(total_times):.0f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep Trip latency benchmark")
    parser.add_argument("--query", default="sensoji temple history", help="Search query")
    parser.add_argument("--location", default="35.7148,139.7967", help="lat,lng")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.query, args.location, args.runs))


if __name__ == "__main__":
    main()
