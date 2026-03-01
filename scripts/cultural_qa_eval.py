#!/usr/bin/env python3
"""
Cultural QA Evaluation Script for Deep Trip.

Runs predefined queries through the LLM and saves results to JSON
for human review. Includes timing metrics for each query.

Usage:
    OPENAI_API_KEY=sk-... python scripts/cultural_qa_eval.py
    OPENAI_API_KEY=sk-... python scripts/cultural_qa_eval.py --output results.json
    OPENAI_API_KEY=sk-... python scripts/cultural_qa_eval.py --model gpt-4o
"""
import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from openai import AsyncOpenAI


SYSTEM_PROMPT = (
    "あなたは「Deep Trip」という東京の観光ガイドAIです。"
    "おもてなしの心を持ち、丁寧な日本語で観光客をご案内してください。"
    "回答は簡潔に、正確な情報を提供してください。"
)

EVAL_QUERIES = [
    {
        "id": "sensoji_basic",
        "query": "浅草寺について教えてください",
        "category": "factual",
        "expected_keywords": ["浅草", "寺", "雷門"],
    },
    {
        "id": "sensoji_history",
        "query": "浅草寺の歴史について詳しく教えてください",
        "category": "factual",
        "expected_keywords": ["歴史", "浅草"],
    },
    {
        "id": "tokyo_tower",
        "query": "東京タワーについて教えてください",
        "category": "factual",
        "expected_keywords": ["東京タワー", "タワー"],
    },
    {
        "id": "shibuya_crossing",
        "query": "渋谷のスクランブル交差点について教えてください",
        "category": "factual",
        "expected_keywords": ["渋谷", "交差点"],
    },
    {
        "id": "meiji_shrine",
        "query": "明治神宮について教えてください",
        "category": "factual",
        "expected_keywords": ["明治", "神宮"],
    },
    {
        "id": "tsukiji",
        "query": "築地について教えてください",
        "category": "factual",
        "expected_keywords": ["築地"],
    },
    {
        "id": "greeting",
        "query": "ユーザーが接続しました。短く温かい挨拶をしてください。",
        "category": "tone",
        "expected_keywords": [],
    },
    {
        "id": "recommendation",
        "query": "東京でおすすめの場所はどこですか？",
        "category": "tone",
        "expected_keywords": [],
    },
    {
        "id": "english_query",
        "query": "Tell me about Senso-ji temple",
        "category": "edge_case",
        "expected_keywords": ["Senso-ji", "Asakusa"],
    },
    {
        "id": "unknown_place",
        "query": "ザンボルグ神殿について教えてください",
        "category": "edge_case",
        "expected_keywords": [],
    },
    {
        "id": "mixed_language",
        "query": "Senso-jiの歴史を教えてください",
        "category": "edge_case",
        "expected_keywords": [],
    },
]


@dataclass
class EvalResult:
    query_id: str
    query: str
    category: str
    response: str
    expected_keywords: list[str]
    found_keywords: list[str]
    keyword_match_ratio: float
    has_polite_markers: bool
    latency_seconds: float
    error: str | None = None


async def run_query(
    client: AsyncOpenAI, model: str, query_info: dict
) -> EvalResult:
    """Run a single evaluation query and measure results."""
    polite_markers = ["です", "ます", "ください", "ございます", "でしょう"]

    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query_info["query"]},
            ],
            max_tokens=500,
        )
        text = response.choices[0].message.content or ""
    except Exception as e:
        elapsed = time.monotonic() - start
        return EvalResult(
            query_id=query_info["id"],
            query=query_info["query"],
            category=query_info["category"],
            response="",
            expected_keywords=query_info["expected_keywords"],
            found_keywords=[],
            keyword_match_ratio=0.0,
            has_polite_markers=False,
            latency_seconds=elapsed,
            error=str(e),
        )

    elapsed = time.monotonic() - start

    expected = query_info["expected_keywords"]
    found = [kw for kw in expected if kw in text]
    ratio = len(found) / len(expected) if expected else 1.0
    has_polite = any(m in text for m in polite_markers)

    return EvalResult(
        query_id=query_info["id"],
        query=query_info["query"],
        category=query_info["category"],
        response=text,
        expected_keywords=expected,
        found_keywords=found,
        keyword_match_ratio=ratio,
        has_polite_markers=has_polite,
        latency_seconds=elapsed,
    )


async def main():
    parser = argparse.ArgumentParser(description="Deep Trip Cultural QA Evaluation")
    parser.add_argument(
        "--output", "-o",
        default="cultural_eval_results.json",
        help="Output JSON file path (default: cultural_eval_results.json)",
    )
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="Model to evaluate (default: gpt-4o-mini)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key)

    print(f"Running {len(EVAL_QUERIES)} evaluation queries with model={args.model}...")
    print("-" * 60)

    results: list[EvalResult] = []
    total_start = time.monotonic()

    for i, query_info in enumerate(EVAL_QUERIES, 1):
        print(f"[{i}/{len(EVAL_QUERIES)}] {query_info['id']}: {query_info['query'][:50]}...")
        result = await run_query(client, args.model, query_info)
        results.append(result)

        status = "OK" if not result.error else f"ERROR: {result.error}"
        kw_status = f"keywords={result.keyword_match_ratio:.0%}" if result.expected_keywords else "n/a"
        polite = "polite" if result.has_polite_markers else "casual"
        print(f"    {status} | {kw_status} | {polite} | {result.latency_seconds:.2f}s")

    total_elapsed = time.monotonic() - total_start

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    errors = [r for r in results if r.error]
    factual = [r for r in results if r.category == "factual"]
    tone = [r for r in results if r.category == "tone"]

    avg_kw_ratio = (
        sum(r.keyword_match_ratio for r in factual) / len(factual)
        if factual else 0
    )
    polite_count = sum(1 for r in results if r.has_polite_markers)
    avg_latency = sum(r.latency_seconds for r in results) / len(results) if results else 0

    print(f"Total queries: {len(results)}")
    print(f"Errors: {len(errors)}")
    print(f"Factual keyword match: {avg_kw_ratio:.0%}")
    print(f"Polite tone: {polite_count}/{len(results)}")
    print(f"Avg latency: {avg_latency:.2f}s")
    print(f"Total time: {total_elapsed:.2f}s")

    # Save results
    output = {
        "model": args.model,
        "total_queries": len(results),
        "total_time_seconds": total_elapsed,
        "avg_latency_seconds": avg_latency,
        "factual_keyword_match_ratio": avg_kw_ratio,
        "polite_tone_ratio": polite_count / len(results) if results else 0,
        "errors": len(errors),
        "results": [asdict(r) for r in results],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
