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
│   ├── local_ai.py         # Local Semantic Filtering (sentence-transformers)
│   ├── main.py             # Entry point
│   ├── metrics.py          # Run statistics & logging
│   ├── rss.py              # RSS feed & HTML generation
│   └── utils.py            # Logging & helpers
├── tests/                  # Unit and integration tests
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── metrics_stats.json      # Persistent TTS usage stats
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
- `tests/test_metrics.py`: Verifies metrics calculation and logging.
- `tests/test_rss.py`: Verifies link page generation and display logic.
- `tests/test_regenerate_feed.py`: Verifies the feed regeneration script.
- `tests/test_audio.py`: Verifies TTS voice selection logic.

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
    - `evening_podcast.yml`: Calls `common.yml` with 8 min duration (Daily 02:30 UTC).
    - `tech_daily_podcast.yml`: Calls `common.yml` with `type: tech` (Daily 14:00 UTC).
    - `tech_weekly_podcast.yml`: Calls `common.yml` with `type: tech_weekly` (Saturday 15:00 UTC).
    - `weekly_podcast.yml`: Calls `common.yml` with 20 min duration & 7-day lookback (Saturday 15:00 UTC).

## Architecture

1.  **Fetcher (`src/fetcher.py`)**: Pulls data from RSS feeds defined in `config.yaml` (selected by `feeds` category). Filters by date and keywords.
3.  **Local Filter (`src/local_ai.py`)**:
    - **Stage 1**: Uses `sentence-transformers` (all-MiniLM-L6-v2) to filter candidates locally based on semantic relevance.
    - Reduces 500+ items to a manageable subset (e.g. 50), saving significant API quota.
4.  **Content (`src/content.py`)**:
    - **Stage 2 Filter**: Uses Gemini 2.5 Flash to select the final set of stories (e.g., top 20) with editorial judgment.
    - **Script Gen**: Summarizes the stories into a conversational script.
5.  **Audio (`src/audio.py`)**: Uses Google Cloud TTS to convert the script to audio.
    - Uses SSML for voice control.
    - Supports `wavenet`, `neural`, `studio`, and `chirp3-hd` voice types via config or CLI arguments.
    - Concatenates audio segments using `pydub` (or simple binary concatenation if mp3).
4.  **RSS (`src/rss.py`)**:
    - Generates `feed.xml` compatible with podcast players.
    - Creates HTML "Links" pages for each episode (with friendly display names).
    - Updates `index.html`.
    - Cleans up old files.
6.  **Metrics (`src/metrics.py`)**:
    - Tracks fetch counts and selection rates per source.
    - Logs cumulative stats to `metrics_prod.md` (Production) and `metrics_test.md` (Test).
    - **TTS Usage**: Tracks character counts sent to the TTS API (per run and running total).
    - **Persistence**: Persists running totals in `metrics_stats.json` (tracked in git) to maintain counts across CI runs.
    
7.  **Configuration (`src/config.py`)**:
    - Uses `dataclasses` for type-safe configuration.
    - **Sparse Overrides**: The `processing_overrides` in `config.yaml` support sparse definitions.
        - If an override key (e.g., `daily`) omits a field (e.g., `gemini_model`), it automatically inherits the value from the default `processing` block.
        - This allows `config.yaml` to remain minimal, specifying only what differs from the global default.

## Contributing

1.  Create a feature branch.
2.  Make changes.
3.  Run tests.
4.  Submit a Pull Request.
