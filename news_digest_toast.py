import time
from windows_toasts import Toast, ToastButton, InteractableWindowsToaster


# ============================================================
# WINDOWS TOAST ENGINE
# ============================================================

toaster = InteractableWindowsToaster("Daily News Digest")


# ============================================================
# NEWS DATA
# ============================================================

news_items = [
    {
        "id": "sc_ec_1",
        "title": "🏛️ Supreme Court Scrutinizes EC",
        "body": "CJI demands original records regarding voter inclusion Form 6 modifications.",
        "url": "https://news.google.com"
    },
    {
        "id": "nobel_2",
        "title": "🏆 Nobel Prize in Medicine Awarded",
        "body": "Karl Deisseroth, Peter Hegemann & Georg Nagel win for optogenetics discovery.",
        "url": "https://news.google.com"
    },
    {
        "id": "trade_3",
        "title": "🤝 India & Switzerland Sign Mobility Pact",
        "body": "PM Modi and Swiss President Parmelin seal landmark trade and mobility agreement.",
        "url": "https://news.google.com"
    },
    {
        "id": "hormuz_4",
        "title": "⚓ US Expands Middle East Naval Deployment",
        "body": "Third aircraft carrier strike group deployed amid Strait of Hormuz tensions.",
        "url": "https://news.google.com"
    },
    {
        "id": "atf_5",
        "title": "✈️ ATF Price Spike Drives Airline Surcharges",
        "body": "Carriers revise fuel surcharges following global turbine fuel cost increases.",
        "url": "https://news.google.com"
    }
]


# ============================================================
# DISPLAY NEWS
# ============================================================

def run_digest(stories, delay_seconds=8):

    for index, story in enumerate(stories, start=1):

        toast = Toast()

        # Title + body
        toast.text_fields = [
            story["title"],
            story["body"]
        ]

        # ----------------------------------------------------
        # READ ARTICLE
        # ----------------------------------------------------

        read_button = ToastButton(
            content="Read Article",
            arguments=story["url"],
            launch=story["url"]
        )

        toast.AddAction(read_button)

        # ----------------------------------------------------
        # SHOW TOAST
        # ----------------------------------------------------

        toaster.show_toast(toast)

        print(
            f"Displayed {index}/{len(stories)}: "
            f"{story['title']}"
        )

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        if index < len(stories):
            time.sleep(delay_seconds)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("Starting Daily News Digest...")

    run_digest(
        news_items,
        delay_seconds=8
    )

    print("Daily News Digest completed.")