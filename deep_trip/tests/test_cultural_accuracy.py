"""
Cultural accuracy tests for Deep Trip's Tokyo travel guide.

These tests verify that LLM responses:
  1. Use appropriate omotenashi (Japanese hospitality) tone
  2. Include factually accurate information about Tokyo locations
  3. Handle edge cases like unknown locations and mixed-language queries

Requires: OPENAI_API_KEY environment variable to be set.
Run: pytest deep_trip/tests/test_cultural_accuracy.py -v -s
"""
import os
import re
import pytest
from openai import AsyncOpenAI

SKIP_REASON = "Requires OPENAI_API_KEY environment variable"
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason=SKIP_REASON,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "あなたは「Deep Trip」という東京の観光ガイドAIです。"
    "おもてなしの心を持ち、丁寧な日本語で観光客をご案内してください。"
    "回答は簡潔に、正確な情報を提供してください。"
)

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

TOKYO_LOCATIONS = {
    "浅草寺": {
        "query": "浅草寺について教えてください",
        "expected_keywords": ["浅草", "寺", "雷門", "仲見世"],
        "description": "Senso-ji temple in Asakusa",
    },
    "東京タワー": {
        "query": "東京タワーについて教えてください",
        "expected_keywords": ["東京タワー", "タワー"],
        "description": "Tokyo Tower",
    },
    "渋谷スクランブル交差点": {
        "query": "渋谷のスクランブル交差点について教えてください",
        "expected_keywords": ["渋谷", "交差点", "スクランブル"],
        "description": "Shibuya Scramble Crossing",
    },
    "明治神宮": {
        "query": "明治神宮について教えてください",
        "expected_keywords": ["明治", "神宮"],
        "description": "Meiji Shrine",
    },
    "築地市場": {
        "query": "築地について教えてください",
        "expected_keywords": ["築地"],
        "description": "Tsukiji Market area",
    },
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def ask_llm(query: str, system_prompt: str = SYSTEM_PROMPT) -> str:
    """Send a query to the LLM and return the response text."""
    client = AsyncOpenAI()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Omotenashi tone tests
# ---------------------------------------------------------------------------

class TestOmotenashiTone:
    """Verify that responses use polite Japanese (desu/masu form)."""

    @pytest.mark.asyncio
    async def test_polite_form_in_location_response(self):
        """Response about a location should use polite Japanese."""
        response = await ask_llm("浅草寺について教えてください")
        # Check for at least one polite form marker
        polite_markers = ["です", "ます", "ください", "ございます", "でしょう"]
        found = any(m in response for m in polite_markers)
        assert found, (
            f"Response lacks polite Japanese markers. Response: {response[:200]}"
        )

    @pytest.mark.asyncio
    async def test_polite_form_in_greeting(self):
        """Greeting response should use polite Japanese."""
        response = await ask_llm("ユーザーが接続しました。短く温かい挨拶をしてください。")
        polite_markers = ["です", "ます", "ください", "ございます"]
        found = any(m in response for m in polite_markers)
        assert found, (
            f"Greeting lacks polite Japanese markers. Response: {response[:200]}"
        )

    @pytest.mark.asyncio
    async def test_no_casual_speech(self):
        """Response should not use overly casual forms like だ/だよ/じゃん."""
        response = await ask_llm("東京でおすすめの場所はどこですか？")
        # Very casual endings that would be inappropriate for a guide
        casual_markers = ["だぜ", "じゃん", "だろ？", "だよな"]
        found_casual = [m for m in casual_markers if m in response]
        assert not found_casual, (
            f"Response uses overly casual forms: {found_casual}. "
            f"Response: {response[:200]}"
        )


# ---------------------------------------------------------------------------
# Factual accuracy tests
# ---------------------------------------------------------------------------

class TestFactualAccuracy:
    """Verify that responses contain expected factual keywords for Tokyo locations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "location_name",
        list(TOKYO_LOCATIONS.keys()),
        ids=list(TOKYO_LOCATIONS.keys()),
    )
    async def test_location_keywords(self, location_name):
        """Response about a Tokyo location should include expected keywords."""
        info = TOKYO_LOCATIONS[location_name]
        response = await ask_llm(info["query"])

        found_keywords = [kw for kw in info["expected_keywords"] if kw in response]
        assert len(found_keywords) >= 1, (
            f"Response for {location_name} ({info['description']}) "
            f"missing expected keywords. Expected any of: {info['expected_keywords']}. "
            f"Response: {response[:300]}"
        )

    @pytest.mark.asyncio
    async def test_sensoji_historical_detail(self):
        """Senso-ji response should mention historical details."""
        response = await ask_llm("浅草寺の歴史について詳しく教えてください")
        # Should mention at least the founding era or key facts
        historical_markers = ["645", "628", "歴史", "古い", "創建", "飛鳥"]
        found = any(m in response for m in historical_markers)
        assert found, (
            f"Senso-ji response lacks historical markers. Response: {response[:300]}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_location(self):
        """Asking about a non-existent location should still get a polite response."""
        response = await ask_llm("ザンボルグ神殿について教えてください")
        # Should not crash; should respond politely
        assert len(response) > 0
        # Should not confidently fabricate detailed facts about a fake place
        # (just check it responds at all)

    @pytest.mark.asyncio
    async def test_english_query(self):
        """English query should still get a helpful response."""
        response = await ask_llm("Tell me about Senso-ji temple")
        assert len(response) > 0
        # Should mention Senso-ji or Asakusa
        assert any(kw in response for kw in ["Senso-ji", "Asakusa", "浅草", "寺"])

    @pytest.mark.asyncio
    async def test_mixed_language_query(self):
        """Mixed Japanese/English query should be handled."""
        response = await ask_llm("Senso-jiの歴史を教えてください")
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_very_short_query(self):
        """Very short query should still get a response."""
        response = await ask_llm("東京")
        assert len(response) > 0
