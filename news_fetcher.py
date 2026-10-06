import re
import html
import hashlib
import logging
from typing import List, Dict, Any, Optional
import feedparser
import requests

from config import load_config, setup_logger

logger = setup_logger()


def clean_html_snippet(raw_html: str) -> str:
    """Strip HTML tags and unescape HTML entities to produce clean text snippet."""
    if not raw_html:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    # Unescape entities like &amp;, &quot;, &#39;
    clean = html.unescape(clean)
    # Collapse multiple whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def extract_source_from_title(title: str, existing_source: Optional[str] = None) -> tuple[str, str]:
    """
    Google News titles usually end with ' - Source Name'.
    Splits the clean title and source if present.
    """
    if existing_source:
        source = existing_source
        clean_title = title
        if title.endswith(f" - {existing_source}"):
            clean_title = title[:-len(f" - {existing_source}")].strip()
        return clean_title, source

    match = re.search(r"^(.*?)\s*-\s*([^-]+)$", title)
    if match:
        clean_title = match.group(1).strip()
        source = match.group(2).strip()
        return clean_title, source
    return title, existing_source or "Unknown"


def generate_article_id(url: str, title: str) -> str:
    """Generate a deterministic, short unique ID for an article."""
    payload = f"{url.strip()}|{title.strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


class NewsFetcher:
    """Modular Google News RSS fetcher with network resilience and category aggregation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()
        self.categories: List[str] = self.cfg.get("categories", [])
        self.category_urls: Dict[str, str] = self.cfg.get("category_feed_urls", {})
        self.max_per_category: int = self.cfg.get("max_candidates_per_category", 5)
        self.timeout: int = self.cfg.get("request_timeout_seconds", 15)
        self.user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    def fetch_feed_data(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch RSS content with requests timeout and parse with feedparser."""
        try:
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            return feed
        except requests.RequestException as e:
            logger.warning("HTTP request failed for URL %s: %s. Trying direct feedparser...", url, e)
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    return feed
            except Exception as fe:
                logger.error("Direct feedparser fallback also failed for %s: %s", url, fe)
        except Exception as e:
            logger.error("Unexpected error fetching feed %s: %s", url, e)
        return None

    def fetch_category(self, category: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch candidate articles for a single category."""
        url = self.category_urls.get(category)
        if not url:
            logger.warning("No feed URL configured for category: %s", category)
            return []

        logger.info("Fetching RSS feed for category '%s'...", category)
        feed = self.fetch_feed_data(url)

        if not feed or not feed.entries:
            logger.warning("No entries found or failed to fetch category '%s'.", category)
            return []

        limit = limit or self.max_per_category
        articles: List[Dict[str, Any]] = []

        for entry in feed.entries[:limit * 2]:  # parse slightly more to allow filtering
            raw_title = entry.get("title", "").strip()
            if not raw_title or raw_title.lower().startswith("this feed is not available"):
                continue

            raw_link = entry.get("link", "").strip()
            if not raw_link:
                continue

            # Extract source
            src_obj = entry.get("source")
            src_title = ""
            if isinstance(src_obj, dict):
                src_title = src_obj.get("title", "")
            elif hasattr(src_obj, "title"):
                src_title = getattr(src_obj, "title", "")

            clean_title, source_name = extract_source_from_title(raw_title, src_title)

            # Clean snippet / description
            raw_desc = entry.get("summary", "") or entry.get("description", "")
            snippet = clean_html_snippet(raw_desc)

            article_id = generate_article_id(raw_link, clean_title)
            pub_time = entry.get("published", "")

            article = {
                "id": article_id,
                "title": clean_title,
                "raw_title": raw_title,
                "url": raw_link,
                "source": source_name,
                "published_time": pub_time,
                "category": category,
                "raw_description": snippet
            }
            articles.append(article)
            if len(articles) >= limit:
                break

        logger.info("Retrieved %d articles for category '%s'.", len(articles), category)
        return articles

    def fetch_all(self, limit_per_category: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch candidate articles across all configured categories.
        Resilient: if one category fails, continues with remaining categories.
        """
        all_candidates: List[Dict[str, Any]] = []
        logger.info("Starting news collection across %d categories...", len(self.categories))

        for category in self.categories:
            try:
                cat_articles = self.fetch_category(category, limit=limit_per_category)
                all_candidates.extend(cat_articles)
            except Exception as e:
                logger.error("Error fetching category '%s': %s. Continuing with other categories...", category, e)

        logger.info("News collection finished. Total candidate articles fetched: %d", len(all_candidates))
        return all_candidates


if __name__ == "__main__":
    import sys

    print("[TEST] Running NewsFetcher standalone test...")
    fetcher = NewsFetcher()
    candidates = fetcher.fetch_all(limit_per_category=3)

    print(f"\nFetched {len(candidates)} total candidate articles across categories.\n")
    if not candidates:
        print("[ERROR] No articles fetched!")
        sys.exit(1)

    for i, a in enumerate(candidates, 1):
        print(f"{i}. [{a['category']}] {a['title']}")
        print(f"   Source: {a['source']} | Pub: {a['published_time']}")
        print(f"   ID: {a['id']}")
        print(f"   URL: {a['url'][:65]}...")
        if a['raw_description']:
            print(f"   Snippet: {a['raw_description'][:100]}...\n")
        else:
            print()

    print("[TEST] NewsFetcher standalone test PASSED.")
