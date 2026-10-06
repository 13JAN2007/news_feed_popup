import os
import sys
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import BASE_DIR, load_config, setup_logger

logger = setup_logger()


class BaseArticleStorage(ABC):
    """Abstract interface for article storage to allow swappable backends (JSON, SQLite, etc.)."""

    @abstractmethod
    def save_article(self, article: Dict[str, Any]) -> bool:
        """Save an article. Returns True if newly saved, False if already present."""
        pass

    @abstractmethod
    def get_saved_articles(self) -> List[Dict[str, Any]]:
        """Return list of all saved articles."""
        pass

    @abstractmethod
    def is_saved(self, article_id: str) -> bool:
        """Check if an article ID is already saved."""
        pass

    @abstractmethod
    def remove_saved(self, article_id: str) -> bool:
        """Remove a saved article by ID."""
        pass


class JsonArticleStorage(BaseArticleStorage):
    """Local JSON-backed persistent storage for saved articles."""

    def __init__(self, file_path: Optional[Path] = None):
        cfg = load_config()
        self.file_path = file_path or (BASE_DIR / cfg.get("storage_file", "saved_articles.json"))
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Ensure storage file exists with valid JSON array."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_all([])
        else:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        self._write_all([])
            except Exception:
                self._write_all([])

    def _read_all(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read storage file %s: %s", self.file_path, e)
            return []

    def _write_all(self, articles: List[Dict[str, Any]]) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to write storage file %s: %s", self.file_path, e)

    def save_article(self, article: Dict[str, Any]) -> bool:
        """Persist an article to saved_articles.json. Prevents duplicates."""
        articles = self._read_all()
        article_id = str(article.get("id") or article.get("article_id") or "").strip()
        article_url = str(article.get("url") or "").strip()

        # Check for duplicate by id or url
        for existing in articles:
            exist_id = str(existing.get("id") or existing.get("article_id") or "").strip()
            exist_url = str(existing.get("url") or "").strip()
            if (article_id and exist_id == article_id) or (article_url and exist_url == article_url):
                logger.info("Article already saved: '%s' (ID: %s)", article.get("title", "Untitled"), article_id)
                return False

        # Format record
        saved_record = {
            "id": article_id,
            "article_id": article_id,
            "title": article.get("title", "Untitled"),
            "url": article_url,
            "source": article.get("source", "Unknown"),
            "category": article.get("category", "General"),
            "published_time": article.get("published_time") or article.get("published", ""),
            "summary": article.get("summary") or article.get("raw_description", ""),
            "saved_time": datetime.now(timezone.utc).isoformat()
        }

        articles.append(saved_record)
        self._write_all(articles)
        logger.info("Successfully saved article: '%s' (ID: %s)", saved_record["title"], article_id)
        return True

    def get_saved_articles(self) -> List[Dict[str, Any]]:
        return self._read_all()

    def is_saved(self, article_id: str) -> bool:
        articles = self._read_all()
        for item in articles:
            if str(item.get("id") or item.get("article_id")) == str(article_id):
                return True
        return False

    def remove_saved(self, article_id: str) -> bool:
        articles = self._read_all()
        initial_len = len(articles)
        filtered = [
            item for item in articles
            if str(item.get("id") or item.get("article_id")) != str(article_id)
        ]
        if len(filtered) < initial_len:
            self._write_all(filtered)
            logger.info("Removed article with ID %s from saved articles.", article_id)
            return True
        return False


class DigestCache:
    """Caches recent digest stories so external activation handlers can look up articles by ID."""

    def __init__(self, cache_path: Optional[Path] = None):
        cfg = load_config()
        self.cache_path = cache_path or (BASE_DIR / cfg.get("cache_file", "recent_digest_cache.json"))

    def save_cache(self, stories: List[Dict[str, Any]]) -> None:
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(stories, f, indent=2, ensure_ascii=False)
            logger.info("Cached %d digest stories for fast interaction lookup.", len(stories))
        except Exception as e:
            logger.error("Failed to write digest cache %s: %s", self.cache_path, e)

    def get_cached_story(self, article_id: str) -> Optional[Dict[str, Any]]:
        if not self.cache_path.exists():
            return None
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                stories = json.load(f)
                for s in stories:
                    if str(s.get("id") or s.get("article_id")) == str(article_id):
                        return s
        except Exception as e:
            logger.error("Failed to read digest cache %s: %s", self.cache_path, e)
        return None

    def get_all_cached(self) -> List[Dict[str, Any]]:
        if not self.cache_path.exists():
            return []
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read digest cache %s: %s", self.cache_path, e)
            return []


def save_article_by_id(article_id: str) -> bool:
    """Look up an article from cache or session and persist it to saved_articles.json."""
    cache = DigestCache()
    story = cache.get_cached_story(article_id)
    storage = JsonArticleStorage()

    if story:
        return storage.save_article(story)
    else:
        # If not found in cache, still record placeholder with ID so action is not lost
        logger.warning("Article ID %s not found in cache; saving placeholder entry.", article_id)
        return storage.save_article({
            "id": article_id,
            "title": f"Saved Article ({article_id})",
            "url": "",
            "source": "Cache Miss",
            "category": "Unknown",
            "published_time": "",
            "summary": "Article details were not available in local cache."
        })


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage saved articles for News Digest")
    parser.add_argument("--save", type=str, help="Save an article by ID from cache")
    parser.add_argument("--list", action="store_true", help="List all saved articles")
    parser.add_argument("--test", action="store_true", help="Run independent storage self-test")
    args = parser.parse_args()

    storage = JsonArticleStorage()

    if args.test:
        print("[TEST] Running Storage self-test...")
        test_id = f"test_{int(datetime.now().timestamp())}"
        test_story = {
            "id": test_id,
            "title": "Test AI Article: Breakthrough in Deep Learning",
            "url": "https://example.com/ai-breakthrough",
            "source": "Tech Science Daily",
            "category": "Artificial Intelligence",
            "published_time": "Tue, 06 Oct 2026 10:00:00 GMT",
            "summary": "Researchers have announced a novel architecture reducing training compute by 50%."
        }

        # 1. Test save
        saved = storage.save_article(test_story)
        assert saved is True, "First save should return True"
        print("  -> Save new article: SUCCESS")

        # 2. Test duplicate prevention
        duplicate = storage.save_article(test_story)
        assert duplicate is False, "Duplicate save should return False"
        print("  -> Duplicate prevention: SUCCESS")

        # 3. Test verification
        assert storage.is_saved(test_id) is True, "is_saved should return True"
        print("  -> is_saved verification: SUCCESS")

        # 4. Clean up test record
        removed = storage.remove_saved(test_id)
        assert removed is True, "remove_saved should return True"
        assert storage.is_saved(test_id) is False, "Article should be removed"
        print("  -> Cleanup test article: SUCCESS")

        print("[TEST] All Storage tests passed cleanly!")
        sys.exit(0)

    if args.save:
        res = save_article_by_id(args.save)
        print(f"Article '{args.save}' save result: {res}")
        sys.exit(0)

    if args.list:
        saved_items = storage.get_saved_articles()
        print(f"Total Saved Articles: {len(saved_items)}")
        for i, item in enumerate(saved_items, 1):
            print(f"{i}. [{item.get('category')}] {item.get('title')} ({item.get('source')})")
            print(f"   URL: {item.get('url')}")
            print(f"   Saved At: {item.get('saved_time')}\n")
        sys.exit(0)

    parser.print_help()
