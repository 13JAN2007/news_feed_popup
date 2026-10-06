import os
import json
import logging
from typing import List, Dict, Any, Optional

from config import load_config, get_gemini_api_key, setup_logger

logger = setup_logger()


class AISummarizer:
    """
    Summarizes news articles using Gemini API with structured JSON output
    and automatic fallback to RSS metadata if Gemini is unavailable.
    """

    def __init__(self, model_name: Optional[str] = None):
        cfg = load_config()
        self.model_name = model_name or cfg.get("gemini_model", "gemini-2.5-flash")
        self.api_key = get_gemini_api_key()
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Gemini client with model '%s'.", self.model_name)
            except Exception as e:
                logger.error("Failed to initialize Google GenAI client: %s", e)
        else:
            logger.warning("No GEMINI_API_KEY configured. System will use RSS snippet fallback mode.")

    def is_gemini_available(self) -> bool:
        """Check if Gemini client is initialized with an API key."""
        return bool(self._client and self.api_key)

    def _build_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Construct structured prompt for Gemini with strict requirements."""
        items_payload = []
        for a in articles:
            items_payload.append({
                "id": a.get("id"),
                "category": a.get("category"),
                "source": a.get("source"),
                "title": a.get("title"),
                "published_time": a.get("published_time"),
                "snippet": a.get("raw_description", "")
            })

        prompt = f"""You are a professional, objective news digest editor.
Your task is to summarize the following news items into concise, engaging daily digest notifications.

INPUT ARTICLES:
{json.dumps(items_payload, indent=2, ensure_ascii=False)}

GUIDELINES FOR EACH ARTICLE:
1. Summary must be 1 to 3 concise, highly readable sentences.
2. Be strictly factual and neutral. No unnecessary opinion or speculation.
3. Do not invent details not present in the title, snippet, or metadata.
4. If details are uncertain in the snippet, preserve that uncertainty.
5. Do not claim to have read the full article body if only RSS metadata is provided.
6. Rate the global/national importance from 1 to 10 (integer).

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON array matching this exact schema:
[
  {{
    "id": "original article id string",
    "title": "Clean, punchy headline",
    "summary": "1-3 concise factual sentences",
    "category": "Category name",
    "importance": 8
  }}
]
"""
        return prompt

    def summarize_with_gemini(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Call Gemini to summarize articles and parse JSON output."""
        if not self._client:
            raise RuntimeError("Gemini client is not initialized or GEMINI_API_KEY is missing.")

        prompt = self._build_prompt(articles)
        logger.info("Sending %d articles to Gemini (%s) for summarization...", len(articles), self.model_name)

        try:
            from google.genai import types

            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            response_text = response.text.strip()
            # Parse JSON
            parsed_data = json.loads(response_text)
            if not isinstance(parsed_data, list):
                raise ValueError("Expected JSON array from Gemini response")

            logger.info("Successfully received Gemini summary for %d articles.", len(parsed_data))

            # Merge with original articles
            id_to_summary = {str(item.get("id")): item for item in parsed_data}
            summarized_articles = []
            for a in articles:
                aid = str(a.get("id"))
                sum_info = id_to_summary.get(aid, {})
                merged = a.copy()
                merged["summary_title"] = sum_info.get("title") or a.get("title")
                merged["summary"] = sum_info.get("summary") or self._fallback_summary(a)
                merged["importance"] = sum_info.get("importance", 5)
                summarized_articles.append(merged)

            return summarized_articles

        except Exception as e:
            # Do NOT log API key
            logger.error("Gemini summarization failed: %s. Falling back to RSS metadata.", e)
            return self.summarize_with_fallback(articles)

    def _fallback_summary(self, article: Dict[str, Any]) -> str:
        """Create a clean fallback summary from RSS snippet and metadata."""
        snippet = article.get("raw_description", "").strip()
        source = article.get("source", "").strip()
        category = article.get("category", "")

        if snippet and len(snippet) > 20:
            # Truncate at sentence or ~180 chars if too long
            if len(snippet) > 220:
                truncated = snippet[:220].rsplit(" ", 1)[0] + "..."
                return f"{truncated} (Reported by {source or 'News Desk'})"
            return f"{snippet} (Reported by {source or 'News Desk'})"

        return f"Latest development in {category}. Read the full report via {source or 'original publisher'}."

    def summarize_with_fallback(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback summarization using RSS titles and cleaned snippets."""
        logger.info("Generating fallback summaries from RSS snippets for %d articles.", len(articles))
        results = []
        for a in articles:
            merged = a.copy()
            merged["summary_title"] = a.get("title")
            merged["summary"] = self._fallback_summary(a)
            merged["importance"] = 5
            results.append(merged)
        return results

    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Public entrypoint: Uses Gemini if configured; falls back gracefully if absent or on error.
        """
        if not articles:
            return []

        if self.is_gemini_available():
            try:
                return self.summarize_with_gemini(articles)
            except Exception as e:
                logger.error("Error in summarize_with_gemini: %s. Using fallback.", e)
                return self.summarize_with_fallback(articles)
        else:
            return self.summarize_with_fallback(articles)


if __name__ == "__main__":
    import sys

    print("[TEST] Running AISummarizer standalone test...")
    sample_articles = [
        {
            "id": "sample_1",
            "title": "Quantum Computing Breakthrough Announced by Research Lab",
            "url": "https://example.com/quantum",
            "source": "Science Today",
            "category": "Science",
            "published_time": "Tue, 06 Oct 2026 09:00:00 GMT",
            "raw_description": "Physicists have sustained a coherent qubit state for over ten minutes at room temperature, unlocking new possibilities for commercial quantum processors."
        },
        {
            "id": "sample_2",
            "title": "Global Markets Rally as Tech Stocks Gain",
            "url": "https://example.com/markets",
            "source": "Market Watch",
            "category": "Business",
            "published_time": "Tue, 06 Oct 2026 08:30:00 GMT",
            "raw_description": "Key tech indices climbed 2.4% following strong quarterly earnings and optimistic revenue guidance across semiconductor leaders."
        }
    ]

    summarizer = AISummarizer()
    print(f"Gemini Available: {summarizer.is_gemini_available()}")

    # Test summarization (will use Gemini if key exists, or fallback if absent)
    results = summarizer.summarize_articles(sample_articles)

    print(f"\nSummarized {len(results)} articles:\n")
    for i, res in enumerate(results, 1):
        print(f"{i}. Title: {res.get('summary_title')}")
        print(f"   Category: {res.get('category')}")
        print(f"   Summary: {res.get('summary')}")
        print(f"   Importance: {res.get('importance')}\n")

    assert len(results) == 2, "Expected 2 summarized articles"
    print("[TEST] AISummarizer standalone test PASSED.")
