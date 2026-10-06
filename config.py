import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env if present
load_dotenv(dotenv_path=BASE_DIR / ".env")

CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "Daily News Digest",
    "aumid": "NewsDigest.DesktopToastApp",
    "stories_count": 5,
    "delay_between_notifications_seconds": 8,
    "digest_interaction_window_seconds": 25,
    "storage_file": "saved_articles.json",
    "cache_file": "recent_digest_cache.json",
    "log_file": "logs/news_digest.log",
    "gemini_model": "gemini-2.5-flash",
    "categories": [
        "India",
        "World",
        "Technology",
        "Artificial Intelligence",
        "Science",
        "Business"
    ],
    "category_feed_urls": {
        "India": "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en",
        "World": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en",
        "Technology": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
        "Artificial Intelligence": "https://news.google.com/rss/search?q=Artificial+Intelligence&hl=en-US&gl=US&ceid=US:en",
        "Science": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en",
        "Business": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
    },
    "max_candidates_per_category": 5,
    "request_timeout_seconds": 15
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json with fallback defaults."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            print(f"[WARNING] Failed to parse {CONFIG_PATH}: {e}. Using defaults.")
    return cfg


def get_gemini_api_key() -> str:
    """Retrieve Gemini API key from environment, never hard-coded."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return key


def setup_logger(log_relative_path: str = "logs/news_digest.log") -> logging.Logger:
    """Configure centralized logger with file and console handlers."""
    logger = logging.getLogger("NewsDigest")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_file_path = BASE_DIR / log_relative_path
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
