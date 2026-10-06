import re
import string
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from config import load_config, setup_logger

logger = setup_logger()

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "did",
    "do", "does", "doing", "don't", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "were", "weren't", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "won't", "would", "you", "your", "yours",
    "yourself", "yourselves", "live", "updates", "breaking"
}


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, remove punctuation, strip extra whitespace."""
    if not title:
        return ""
    # Remove source suffix if still attached
    if " - " in title:
        title = title.rsplit(" - ", 1)[0]
    title = title.lower()
    # Replace punctuation with space
    title = re.sub(r"[^\w\s]", " ", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def get_title_tokens(title: str) -> Set[str]:
    """Extract significant keywords from normalized title."""
    norm = normalize_title(title)
    words = norm.split()
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def calculate_jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Compute Jaccard similarity index between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters like ?oc=5, utm_*, etc."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        # Strip tracking params
        filtered_query = {
            k: v for k, v in query.items()
            if not k.startswith("utm_") and k not in {"oc", "fr_unfepa"}
        }
        clean_query = urlencode(filtered_query, doseq=True)
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            ""  # drop fragment
        ))
    except Exception:
        return url.strip().lower()


def parse_published_datetime(pub_str: str) -> Optional[datetime]:
    """Parse RFC 822 or ISO publication timestamp safely."""
    if not pub_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class BaseRanker(ABC):
    """Abstract base class for news ranking algorithms."""

    @abstractmethod
    def rank_and_select(self, articles: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
        """Rank candidate articles and return top selected stories."""
        pass


class ScoredNewsRanker(BaseRanker):
    """
    Rule-based scoring ranker that balances recency, category diversity,
    source credibility, snippet quality, and penalizes cross-article duplication.
    """

    def __init__(self, similarity_threshold: float = 0.45):
        self.similarity_threshold = similarity_threshold

    def calculate_recency_score(self, pub_str: str) -> float:
        dt = parse_published_datetime(pub_str)
        if not dt:
            return 10.0  # default baseline
        now = datetime.now(timezone.utc)
        age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)

        if age_hours <= 3.0:
            return 40.0
        elif age_hours <= 6.0:
            return 30.0
        elif age_hours <= 12.0:
            return 20.0
        elif age_hours <= 24.0:
            return 15.0
        elif age_hours <= 48.0:
            return 8.0
        else:
            return 3.0

    def calculate_article_score(self, article: Dict[str, Any]) -> float:
        score = 0.0

        # 1. Recency
        score += self.calculate_recency_score(article.get("published_time", ""))

        # 2. Source presence
        src = article.get("source", "").strip()
        if src and src.lower() != "unknown":
            score += 15.0

        # 3. Snippet availability
        desc = article.get("raw_description", "").strip()
        if desc and len(desc) > 30:
            score += 10.0

        # 4. Title quality (penalize extreme brevity)
        title = article.get("title", "").strip()
        if len(title) >= 20:
            score += 10.0
        elif len(title) < 10:
            score -= 15.0

        return score

    def rank_and_select(self, articles: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
        if not articles:
            return []

        # Score all articles
        for a in articles:
            a["_score"] = self.calculate_article_score(a)
            a["_tokens"] = get_title_tokens(a.get("title", ""))

        # Group by category to ensure representation
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for a in articles:
            cat = a.get("category", "General")
            by_category.setdefault(cat, []).append(a)

        # Sort within each category by score descending
        for cat in by_category:
            by_category[cat].sort(key=lambda x: x["_score"], reverse=True)

        selected: List[Dict[str, Any]] = []
        selected_tokens: List[Set[str]] = []

        def is_too_similar_to_selected(candidate_tokens: Set[str]) -> bool:
            for s_tok in selected_tokens:
                if calculate_jaccard_similarity(candidate_tokens, s_tok) >= self.similarity_threshold:
                    return True
            return False

        # Phase 1: Round-robin pick the top non-duplicate story from each category for broad coverage
        for cat, cat_items in by_category.items():
            for item in cat_items:
                tokens = item["_tokens"]
                if not is_too_similar_to_selected(tokens):
                    selected.append(item)
                    selected_tokens.append(tokens)
                    break
            if len(selected) >= count:
                break

        # Phase 2: If we still need more stories to reach target count, pick remaining top scored overall
        if len(selected) < count:
            all_sorted = sorted(articles, key=lambda x: x["_score"], reverse=True)
            for item in all_sorted:
                if item in selected:
                    continue
                tokens = item["_tokens"]
                if not is_too_similar_to_selected(tokens):
                    selected.append(item)
                    selected_tokens.append(tokens)
                if len(selected) >= count:
                    break

        # Clean temporary internal fields
        for a in articles:
            a.pop("_score", None)
            a.pop("_tokens", None)

        return selected[:count]


class NewsProcessor:
    """Orchestrates article deduplication and selection."""

    def __init__(self, ranker: Optional[BaseRanker] = None, similarity_threshold: float = 0.45):
        self.ranker = ranker or ScoredNewsRanker(similarity_threshold=similarity_threshold)
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate candidates based on:
        1. Normalized URL matching
        2. Normalized title Jaccard keyword similarity
        """
        initial_count = len(articles)
        unique_articles: List[Dict[str, Any]] = []
        seen_urls: Set[str] = set()
        seen_title_tokens: List[Set[str]] = []

        for article in articles:
            # 1. Check URL
            norm_url = normalize_url(article.get("url", ""))
            if norm_url and norm_url in seen_urls:
                logger.debug("Dropped duplicate URL: %s", article.get("title"))
                continue

            # 2. Check title similarity
            tokens = get_title_tokens(article.get("title", ""))
            is_dup = False
            for prev_tokens in seen_title_tokens:
                sim = calculate_jaccard_similarity(tokens, prev_tokens)
                if sim >= self.similarity_threshold:
                    logger.debug("Dropped duplicate story (sim=%.2f): '%s'", sim, article.get("title"))
                    is_dup = True
                    break

            if not is_dup:
                seen_urls.add(norm_url)
                seen_title_tokens.append(tokens)
                unique_articles.append(article)

        removed_count = initial_count - len(unique_articles)
        logger.info("Deduplication completed: %d candidates -> %d unique (removed %d duplicates).",
                    initial_count, len(unique_articles), removed_count)
        return unique_articles

    def select_stories(self, articles: List[Dict[str, Any]], count: int = 5) -> List[Dict[str, Any]]:
        """Deduplicate and select top N stories using the modular ranker."""
        unique_articles = self.deduplicate(articles)
        selected = self.ranker.rank_and_select(unique_articles, count=count)
        logger.info("Selected %d top stories for daily digest.", len(selected))
        return selected


if __name__ == "__main__":
    from news_fetcher import NewsFetcher

    print("[TEST] Running NewsProcessor standalone test...")
    fetcher = NewsFetcher()
    raw_articles = fetcher.fetch_all(limit_per_category=4)

    processor = NewsProcessor()
    selected_stories = processor.select_stories(raw_articles, count=5)

    print(f"\nFinal Selected {len(selected_stories)} Stories for Digest:")
    for i, s in enumerate(selected_stories, 1):
        print(f"{i}. [{s['category']}] {s['title']} ({s['source']})")
        print(f"   Published: {s['published_time']}")
        print(f"   URL: {s['url'][:60]}...\n")

    assert len(selected_stories) > 0, "Should select at least 1 story"
    print("[TEST] NewsProcessor standalone test PASSED.")
