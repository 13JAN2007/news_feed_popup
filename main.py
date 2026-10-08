"""
Daily News Digest - Personal Automated AI News Digest for Windows
==================================================================
Pipeline:
  Task Scheduler / Manual Run
      ↓
  Fetch RSS news (Google News categories)
      ↓
  Collect candidate articles
      ↓
  Deduplicate stories (URL & title similarity)
      ↓
  Rank & select top important stories
      ↓
  Summarize with Gemini (or RSS fallback)
      ↓
  Display Windows Toast Notifications
      ↓
  User can 'Read Article' (direct browser launch) or 'Save for Later' (persistent storage)
"""

import sys
import argparse
import traceback
from typing import Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

from config import load_config, setup_logger, get_gemini_api_key
from news_fetcher import NewsFetcher
from news_processor import NewsProcessor
from ai_summarizer import AISummarizer
from notification_manager import NotificationManager
from storage import JsonArticleStorage, save_article_by_id

logger = setup_logger()


def run_digest(
    stories_count: Optional[int] = None,
    delay_seconds: Optional[int] = None,
    use_ai: bool = True
) -> int:
    """
    Executes the complete daily news digest pipeline.
    Returns 0 on success, non-zero on critical failure.
    """
    cfg = load_config()
    target_count = stories_count or cfg.get("stories_count", 5)

    logger.info("=" * 60)
    logger.info("Starting Daily News Digest run (target count: %d)...", target_count)
    logger.info("=" * 60)

    try:
        # 1. Fetch Candidate Articles
        fetcher = NewsFetcher(cfg)
        candidates = fetcher.fetch_all()

        if not candidates:
            logger.warning("No candidate articles could be fetched. Exiting digest cleanly.")
            return 0

        logger.info("Collected %d total candidate articles across categories.", len(candidates))

        # 2. Deduplicate & Select Top Stories
        processor = NewsProcessor()
        selected_stories = processor.select_stories(candidates, count=target_count)

        if not selected_stories:
            logger.warning("No stories selected after processing. Exiting cleanly.")
            return 0

        logger.info("Selected %d stories for summarization.", len(selected_stories))

        # 3. AI Summarization (Gemini or Fallback)
        if use_ai:
            summarizer = AISummarizer()
            summarized_stories = summarizer.summarize_articles(selected_stories)
        else:
            logger.info("AI summarization disabled by flag. Using RSS metadata.")
            summarizer = AISummarizer()
            summarized_stories = summarizer.summarize_with_fallback(selected_stories)

        # 4. Display Toast Notifications
        notif_manager = NotificationManager(cfg)
        if delay_seconds is not None:
            notif_manager.delay_seconds = delay_seconds

        notif_manager.display_digest(summarized_stories)

        logger.info("Daily News Digest completed successfully.")
        return 0

    except Exception as e:
        logger.error("Unexpected error during news digest execution: %s", e)
        logger.error(traceback.format_exc())
        return 1


def run_all_tests() -> bool:
    """
    Runs self-tests for all major components:
    1. Storage (save, duplicate prevention, verification)
    2. News Fetching
    3. News Processing & Deduplication
    4. AI Summarizer (fallback + Gemini if key present)
    5. Toast Notification construction
    """
    print("\n" + "=" * 60)
    print("RUNNING ALL COMPONENT TESTS")
    print("=" * 60)

    # 1. Storage Test
    print("\n[TEST 1/5] Testing Storage Component...")
    storage = JsonArticleStorage()
    test_id = "test_e2e_id"
    test_record = {
        "id": test_id,
        "title": "E2E Test News Article",
        "url": "https://news.google.com",
        "source": "Test Source",
        "category": "Technology",
        "published_time": "Now",
        "summary": "This is a test summary."
    }
    assert storage.save_article(test_record) is True, "First save failed"
    assert storage.save_article(test_record) is False, "Duplicate prevention failed"
    assert storage.is_saved(test_id) is True, "is_saved failed"
    assert storage.remove_saved(test_id) is True, "remove_saved failed"
    print("  -> [OK] Storage Component: PASSED")

    # 2. News Fetcher Test
    print("\n[TEST 2/5] Testing News Fetcher Component...")
    fetcher = NewsFetcher()
    test_articles = fetcher.fetch_all(limit_per_category=2)
    assert len(test_articles) > 0, "News Fetcher returned 0 articles"
    print(f"  -> [OK] News Fetcher Component: PASSED ({len(test_articles)} articles retrieved)")

    # 3. News Processor Test
    print("\n[TEST 3/5] Testing News Processor & Deduplication...")
    processor = NewsProcessor()
    selected = processor.select_stories(test_articles, count=3)
    assert len(selected) > 0, "News Processor selected 0 stories"
    print(f"  -> [OK] News Processor Component: PASSED ({len(selected)} stories selected)")

    # 4. AI Summarizer Test
    print("\n[TEST 4/5] Testing AI Summarizer...")
    summarizer = AISummarizer()
    summarized = summarizer.summarize_articles(selected[:2])
    assert len(summarized) == 2, "AI Summarizer did not return expected count"
    assert "summary" in summarized[0], "Summary field missing"
    print("  -> [OK] AI Summarizer Component: PASSED")

    # 5. Notification Toast Construction Test
    print("\n[TEST 5/5] Testing Notification Toast Construction...")
    notif_manager = NotificationManager()
    toast = notif_manager.create_story_toast(summarized[0])
    assert len(toast.text_fields) == 2, "Toast must have title and body"
    assert len(toast.actions) >= 1, "Toast must have actions"
    print("  -> [OK] Notification Construction: PASSED")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY (5/5)!")
    print("=" * 60 + "\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily News Digest - Automated AI News Notifications for Windows"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run comprehensive self-tests across all components"
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Fetch and print top stories to console without sending toast notifications"
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Run digest without calling Gemini (uses clean RSS metadata)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of stories to include in this digest"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=None,
        help="Delay in seconds between toast notifications"
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Save an article by ID to saved_articles.json"
    )
    parser.add_argument(
        "--save-url",
        type=str,
        help="Handle custom protocol URL from Windows Toast (e.g. newsdigest://save?id=XYZ)"
    )
    parser.add_argument(
        "--list-saved",
        action="store_true",
        help="List all saved articles"
    )

    args = parser.parse_args()

    # Route CLI actions
    if args.test:
        success = run_all_tests()
        sys.exit(0 if success else 1)

    if args.save_url:
        from urllib.parse import urlparse, parse_qs
        url_input = args.save_url.strip()
        article_id = None
        if "id=" in url_input:
            try:
                qs = parse_qs(urlparse(url_input).query)
                if "id" in qs and qs["id"]:
                    article_id = qs["id"][0].strip()
            except Exception:
                pass
        if not article_id and "save:" in url_input:
            article_id = url_input.split("save:", 1)[1].strip()
        if not article_id and url_input.startswith("newsdigest:"):
            clean_part = url_input.replace("newsdigest://", "").replace("newsdigest:", "")
            if "id=" in clean_part:
                article_id = clean_part.split("id=", 1)[1].split("&", 1)[0].strip()

        if article_id:
            res = save_article_by_id(article_id)
            logger.info("Protocol activation save result for ID '%s': %s", article_id, res)
            try:
                notif = NotificationManager()
                notif.show_save_confirmation(article_id, already_saved=not res)
            except Exception as ce:
                logger.debug("Failed to pop save confirmation: %s", ce)
        else:
            logger.warning("Could not extract article ID from protocol URL: %s", url_input)
        sys.exit(0)

    if args.save:
        res = save_article_by_id(args.save)
        print(f"Article '{args.save}' saved: {res}")
        sys.exit(0)

    if args.list_saved:
        storage = JsonArticleStorage()
        items = storage.get_saved_articles()
        print(f"\nSaved Articles ({len(items)}):")
        for i, item in enumerate(items, 1):
            print(f"{i}. [{item.get('category')}] {item.get('title')} ({item.get('source')})")
            print(f"   URL: {item.get('url')}")
            print(f"   Saved At: {item.get('saved_time')}\n")
        sys.exit(0)

    if args.fetch_only:
        cfg = load_config()
        fetcher = NewsFetcher(cfg)
        candidates = fetcher.fetch_all()
        processor = NewsProcessor()
        count = args.count or cfg.get("stories_count", 5)
        selected = processor.select_stories(candidates, count=count)
        summarizer = AISummarizer()
        if args.no_ai or not summarizer.is_gemini_available():
            processed = summarizer.summarize_with_fallback(selected)
        else:
            processed = summarizer.summarize_articles(selected)

        print(f"\n--- DIGEST PREVIEW ({len(processed)} Stories) ---")
        for i, s in enumerate(processed, 1):
            print(f"\n{i}. [{s.get('category')}] {s.get('summary_title') or s.get('title')}")
            print(f"   Source: {s.get('source')} | Published: {s.get('published_time')}")
            print(f"   Summary: {s.get('summary')}")
            print(f"   URL: {s.get('url')}")
        sys.exit(0)

    # Standard Digest Run
    code = run_digest(
        stories_count=args.count,
        delay_seconds=args.delay,
        use_ai=not args.no_ai
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
