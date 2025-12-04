# Developer Guide

This guide is intended for developers contributing to the News Podcast Generator.

## Project Structure

```
news_podcast/
├── .github/workflows/      # GitHub Actions workflows
│   ├── common.yml          # Reusable workflow logic
│   ├── morning_podcast.yml # Morning schedule
│   ├── evening_podcast.yml # Evening schedule
│   └── weekly_podcast.yml  # Weekly schedule
├── assets/                 # Static assets (cover images, etc.)
├── episodes/               # Generated artifacts (audio, scripts, metadata)
├── scripts/                # Utility scripts
│   ├── regenerate_feed.py  # Regenerates RSS feed from metadata
│   └── stage_artifacts.sh  # Stages artifacts for git commit
├── src/                    # Source code
│   ├── __init__.py
│   ├── audio.py            # TTS logic (Google Cloud TTS)
│   ├── config.py           # Configuration loading
│   ├── content.py          # LLM logic (Gemini)
│   ├── fetcher.py          # RSS fetching & filtering
│   ├── main.py             # Entry point
│   ├── rss.py              # RSS feed & HTML generation
│   └── utils.py            # Logging & helpers
├── tests/                  # Unit and integration tests
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
└── README.md               # User documentation
```

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/amullick-git/news_bot.git
    cd news_podcast
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables:**
    Create a `.env` file or export these variables:
    ```bash
    export GOOGLE_API_KEY="your_gemini_api_key"
    export GOOGLE_APPLICATION_CREDENTIALS="path/to/service_account.json"
    ```

## Running Locally

You can run the bot locally using the module syntax:

```bash
# Standard run (uses config.yaml defaults)
python -m src.main

# Custom duration
python -m src.main --duration 5

# Test mode (dry run, saves to test_episodes/)
python -m src.main --test
```

## Testing

We use `pytest` for testing.

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_fetcher.py
```

### Key Tests
- `tests/test_fetcher.py`: Verifies RSS filtering logic (time windows, keywords).
- `tests/test_config.py`: Verifies configuration loading.
- `tests/test_regenerate_feed.py`: Verifies the feed regeneration script.

## CI/CD Workflows

The project uses GitHub Actions for automation. The workflows are modularized to reduce duplication.

1.  **`common.yml`**: A reusable workflow that handles:
    - Checkout & Setup
    - Dependency Installation
    - Authentication (GCP)
    - Running the Bot (via `src.main`)
    - Committing & Pushing Artifacts (MP3s, Scripts, RSS Feed)

2.  **Triggers**:
    - `morning_podcast.yml`: Calls `common.yml` with 15 min duration (Daily 14:30 UTC).
    - `evening_podcast.yml`: Calls `common.yml` with 5 min duration (Daily 02:30 UTC).
    - `weekly_podcast.yml`: Calls `common.yml` with 20 min duration & 7-day lookback (Saturday 15:00 UTC).

## Architecture

1.  **Fetcher (`src/fetcher.py`)**: Pulls data from RSS feeds defined in `config.yaml`. Filters by date and keywords.
2.  **Content (`src/content.py`)**: Uses Gemini 1.5 Flash to:
    - Select the most relevant stories.
    - Summarize them into a conversational script (Host & Reporter).
3.  **Audio (`src/audio.py`)**: Uses Google Cloud TTS to convert the script to audio.
    - Uses SSML for voice control.
    - Concatenates audio segments using `pydub` (or simple binary concatenation if mp3).
4.  **RSS (`src/rss.py`)**:
    - Generates `feed.xml` compatible with podcast players.
    - Creates HTML "Links" pages for each episode.
    - Updates `index.html`.
    - Cleans up old files.

## Contributing

1.  Create a feature branch.
2.  Make changes.
3.  Run tests.
4.  Submit a Pull Request.
