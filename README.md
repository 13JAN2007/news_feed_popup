# Daily News Digest 📰🤖

An automated personal AI Daily News Digest application for Windows. It fetches fresh headlines from Google News RSS feeds, removes duplicates, scores and ranks top stories, generates concise factual summaries using Google Gemini, and delivers interactive Windows Toast notifications directly to your desktop.

---

## Architecture & Pipeline

```text
Task Scheduler (1:00 PM Daily) or Manual Run
                     ↓
        Fetch Google News RSS Feeds
(India, World, Technology, AI, Science, Business)
                     ↓
         Collect Candidate Articles
                     ↓
         Deduplicate & Normalize
  (URL canonicalization + title similarity)
                     ↓
        Modular Scored Ranking
(Recency, Category Diversity, Snippet Quality)
                     ↓
          Gemini AI Summarization
   (1–3 concise sentences, structured JSON)
           (with graceful RSS fallback)
                     ↓
      Windows Toast Notifications
     (InteractableWindowsToaster 1.3.1)
           ↙                   ↘
    [Read Article]       [Save for Later]
 (Direct Browser Link) (saved_articles.json)
```

---

## Features

- **Multi-Category Coverage**: Retrieves top stories across India, World, Technology, Artificial Intelligence, Science, and Business.
- **Smart Deduplication**: Normalizes titles and URLs to prevent identical or cross-category stories from repeating.
- **Modular Scored Ranking**: Guarantees diversity across topics while prioritizing the freshest, most credible stories.
- **Gemini AI Summarization**: Uses Google Gemini to generate 1–3 sentence objective, factual summaries.
- **Fail-Safe Fallbacks**: If Gemini is offline or `GEMINI_API_KEY` is omitted, the app smoothly falls back to cleaned RSS descriptions without failing.
- **Interactable Windows Toasts**:
  - **Read Article**: Launches the full publisher article directly in your default browser.
  - **Save for Later**: Persists articles to local `saved_articles.json` reading list.
- **Silent Background Execution**: Runs via `pythonw.exe` or `run_digest.vbs` without opening command prompt windows.
- **Centralized Logging**: Comprehensive logging to `logs/news_digest.log` with zero credential leakage.

---

## Project Structure

```text
news_feed_popup/
├── main.py                   # Main pipeline orchestrator and CLI entrypoint
├── news_fetcher.py           # RSS fetching with network resilience
├── news_processor.py         # Deduplication & modular scoring ranker
├── ai_summarizer.py          # Gemini AI summarizer with structured JSON & fallback
├── notification_manager.py   # Windows-Toasts notification engine
├── storage.py                # Persistent JSON storage for Save for Later
├── config.py                 # Configuration loader and centralized logger
│
├── config.json               # Application configuration settings
├── .env.example              # Environment variables template
├── .env                      # Local environment file (contains GEMINI_API_KEY)
├── .gitignore                # Excludes secrets, logs, and caches
│
├── saved_articles.json       # Persisted bookmarks saved by user
├── recent_digest_cache.json  # Temporary cache of current digest items
├── run_digest.bat            # Quick command-line execution script
├── run_digest.vbs            # Silent runner for Task Scheduler
│
├── logs/
│   └── news_digest.log       # Application logs
└── README.md                 # Documentation and setup guide
```

---

## Prerequisites

- **Windows 10 or Windows 11**
- **Python 3.13** (or 3.10+)
- Installed packages:
  - `Windows-Toasts==1.3.1`
  - `feedparser`
  - `google-genai`
  - `requests`
  - `python-dotenv`

To install/verify dependencies:
```powershell
pip install Windows-Toasts==1.3.1 feedparser google-genai requests python-dotenv
```

---

## Configuration

### 1. Gemini API Key (`.env`)
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Edit `.env` and insert your Gemini API key from [Google AI Studio](https://aistudio.google.com/):
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(Note: If no API key is provided, the application will automatically run in RSS fallback mode.)*

### 2. Custom Settings (`config.json`)
You can adjust settings in `config.json`:
- `stories_count`: Number of stories to select for each digest (default: `5`).
- `delay_between_notifications_seconds`: Pause between toasts (default: `8`).
- `digest_interaction_window_seconds`: Listening window after digest for button actions (default: `20`).
- `gemini_model`: Model to use (default: `gemini-2.5-flash`).
- `categories`: Active categories list.

---

## Usage

### Run the Interactive Digest
```powershell
python main.py
```

### Preview Top Stories in Terminal (No Toasts)
```powershell
python main.py --fetch-only --count 5
```

### Run Digest without AI (Fast RSS Metadata Mode)
```powershell
python main.py --no-ai
```

### List All Saved Articles
```powershell
python main.py --list-saved
# or
python storage.py --list
```

### Manually Save an Article by ID
```powershell
python main.py --save <article_id>
```

---

## Testing Components

Each component includes an independent test mode so you can verify features in isolation:

1. **Run Full Test Suite (All 5 components)**:
   ```powershell
   python main.py --test
   ```

2. **Test News Fetching Independently**:
   ```powershell
   python news_fetcher.py
   ```

3. **Test Deduplication & Ranking Independently**:
   ```powershell
   python news_processor.py
   ```

4. **Test AI Summarizer Independently**:
   ```powershell
   python ai_summarizer.py
   ```

5. **Test Toast Notifications Independently**:
   ```powershell
   python notification_manager.py
   ```

6. **Test Storage & Bookmark Persistence**:
   ```powershell
   python storage.py --test
   ```

---

## Windows Task Scheduler Setup (Daily at 1:00 PM)

To run the Daily News Digest automatically every day at 1:00 PM silently in the background:

1. Open **Task Scheduler** (`Win + R`, type `taskschd.msc` and press Enter).
2. Click **Create Task...** in the right-hand panel.
3. On the **General** tab:
   - **Name**: `Daily News Digest`
   - **Description**: `Automated AI Daily News Digest Toast Notifications`
   - **Security options**: Select **"Run only when user is logged on"** *(Critical: Windows toast notifications require an active logged-on desktop session to render)*.
4. On the **Triggers** tab:
   - Click **New...**
   - **Begin the task**: `On a schedule`
   - Settings: `Daily`
   - **Start**: Set time to `1:00:00 PM`
   - **Recur every**: `1` days
   - Click **OK**.
5. On the **Actions** tab:
   - Click **New...**
   - **Action**: `Start a program`
   - **Program/script**: 
     ```text
     pythonw.exe
     ```
     *(Or full path: `C:\Users\Arnav Sharma\AppData\Local\Programs\Python\Python313\pythonw.exe`)*
   - **Add arguments**:
     ```text
     "D:\python exploration\news_feed_popup\main.py"
     ```
   - **Start in**:
     ```text
     D:\python exploration\news_feed_popup
     ```
   - Click **OK**.
6. On the **Conditions** tab:
   - Check **"Start only if the following network connection is available: Any connection"** (optional, recommended for internet feeds).
7. On the **Settings** tab:
   - Check **"Allow task to be run on demand"**.
   - Check **"If the running task does not end when requested, force it to stop"**.
   - Click **OK**.

You can right-click the newly created task in Task Scheduler and click **Run** to test it immediately!
