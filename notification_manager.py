import time
import logging
import winreg
from typing import List, Dict, Any, Optional, Callable
from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastButton,
    ToastActivatedEventArgs
)

from config import load_config, setup_logger
from storage import JsonArticleStorage, DigestCache, save_article_by_id

logger = setup_logger()

CATEGORY_ICONS = {
    "India": "🇮🇳",
    "World": "🌍",
    "Technology": "💻",
    "Artificial Intelligence": "🤖",
    "Science": "🔬",
    "Business": "📈",
    "General": "📰"
}


def register_app_aumid(app_id: str, app_name: str) -> bool:
    """
    Registers the application AUMID in HKCU to ensure Windows recognizes
    the app and dispatches interactive toast actions properly.
    Does NOT require administrator elevation.
    """
    key_path = f"SOFTWARE\\Classes\\AppUserModelId\\{app_id}"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, app_name)
        logger.debug("Registered AUMID '%s' with display name '%s'.", app_id, app_name)
        return True
    except Exception as e:
        logger.warning("Could not register AUMID '%s': %s", app_id, e)
        return False


class NotificationManager:
    """
    Manages Windows toast notifications using InteractableWindowsToaster.
    Preserves direct URL launch behavior for Read Article and handles Save for Later actions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()
        self.app_name = self.cfg.get("app_name", "Daily News Digest")
        self.aumid = self.cfg.get("aumid", "NewsDigest.DesktopToastApp")
        self.delay_seconds = self.cfg.get("delay_between_notifications_seconds", 8)
        self.interaction_window = self.cfg.get("digest_interaction_window_seconds", 20)

        # Register AUMID in HKCU for interactive action delivery
        register_app_aumid(self.aumid, self.app_name)

        # Initialize InteractableWindowsToaster
        try:
            self.toaster = InteractableWindowsToaster(self.app_name, notifierAUMID=self.aumid)
        except Exception as e:
            logger.warning("Failed to initialize toaster with custom AUMID (%s). Falling back to default.", e)
            self.toaster = InteractableWindowsToaster(self.app_name)

        self.storage = JsonArticleStorage()
        self.cache = DigestCache()

    def _handle_toast_activated(self, event_args: ToastActivatedEventArgs) -> None:
        """Callback invoked when user interacts with a toast button without direct protocol launch."""
        args_str = event_args.arguments or ""
        logger.info("Toast action activated: '%s'", args_str)

        if args_str.startswith("save:"):
            article_id = args_str.split("save:", 1)[1].strip()
            success = save_article_by_id(article_id)
            if success:
                logger.info("Save-for-later succeeded for article ID: %s", article_id)
                self._show_save_confirmation(article_id)
            else:
                logger.info("Article ID %s was already saved.", article_id)

    def _show_save_confirmation(self, article_id: str) -> None:
        """Show a small non-intrusive toast confirming the article was saved."""
        try:
            story = self.cache.get_cached_story(article_id)
            title = story.get("title", "Article") if story else "Article"
            confirm_toast = Toast([
                "Bookmark Saved",
                f"Saved to your reading list: {title[:60]}..."
            ])
            self.toaster.show_toast(confirm_toast)
        except Exception as e:
            logger.debug("Failed to display save confirmation toast: %s", e)

    def create_story_toast(self, story: Dict[str, Any]) -> Toast:
        """Construct a formatted Toast with Read Article and Save for Later buttons."""
        category = story.get("category", "General")
        icon = CATEGORY_ICONS.get(category, "📰")

        display_title = f"{icon} {story.get('summary_title') or story.get('title')}"
        display_body = story.get("summary") or story.get("raw_description", "")
        article_url = story.get("url", "https://news.google.com")
        article_id = story.get("id", "")

        toast = Toast()
        toast.text_fields = [
            display_title,
            display_body
        ]

        # ----------------------------------------------------
        # 1. READ ARTICLE (Tested direct URL protocol launch)
        # ----------------------------------------------------
        read_button = ToastButton(
            content="Read Article",
            arguments=article_url,
            launch=article_url
        )
        toast.AddAction(read_button)

        # ----------------------------------------------------
        # 2. SAVE FOR LATER (Interactable action)
        # ----------------------------------------------------
        if article_id:
            save_button = ToastButton(
                content="Save for Later",
                arguments=f"save:{article_id}"
            )
            toast.AddAction(save_button)

        # Attach activation listener
        toast.on_activated = self._handle_toast_activated

        return toast

    def display_digest(self, stories: List[Dict[str, Any]]) -> None:
        """
        Sequentially display a digest of stories with pauses between them.
        Caches stories for interaction lookup and listens for button activations.
        """
        if not stories:
            logger.warning("No stories to display.")
            return

        # Cache stories so save-by-id lookup works
        self.cache.save_cache(stories)

        total = len(stories)
        logger.info("Beginning toast digest presentation (%d stories, %ds interval)...", total, self.delay_seconds)

        for index, story in enumerate(stories, start=1):
            try:
                toast = self.create_story_toast(story)
                self.toaster.show_toast(toast)

                logger.info(
                    "Displayed notification [%d/%d] [%s]: %s",
                    index, total, story.get("category", "General"), story.get("title", "")
                )
            except Exception as e:
                logger.error("Failed to display toast for story '%s': %s", story.get("title"), e)

            # Pause between notifications
            if index < total:
                time.sleep(self.delay_seconds)

        # Keep active briefly to capture user clicks on recent toasts
        if self.interaction_window > 0:
            logger.info("Listening for user interactions for %d seconds...", self.interaction_window)
            time.sleep(self.interaction_window)

        logger.info("Toast digest presentation completed.")


if __name__ == "__main__":
    print("[TEST] Running NotificationManager standalone test...")
    manager = NotificationManager()

    test_story = {
        "id": "notif_test_1",
        "title": "NASA Rover Detects Ancient Lake Evidence on Mars",
        "summary": "Perseverance has uncovered mineral formations indicating water flowed continuously for millions of years. (Reported by Science Daily)",
        "url": "https://www.google.com",
        "source": "NASA JPL",
        "category": "Science",
        "published_time": "Tue, 06 Oct 2026 12:00:00 GMT"
    }

    print("Showing 1 test notification with 'Read Article' and 'Save for Later'...")
    # Cache it first
    manager.cache.save_cache([test_story])
    toast = manager.create_story_toast(test_story)
    manager.toaster.show_toast(toast)
    print("Toast sent! Sleeping 10 seconds to allow interaction testing...")
    time.sleep(10)
    print("[TEST] NotificationManager test completed.")
