# News Podcast Generator

This project is an automated tool that fetches news from various RSS feeds, filters them based on keywords and semantic relevance using Google Gemini, generates a script, and converts it into a podcast-style audio file using Google Cloud Text-to-Speech.

## Features

- **RSS Feed Fetching**: Pulls news from BBC, NYT, NDTV, Hacker News, The Verge, CNBC, NPR, and more.
- **Smart Filtering**:
    - Filters articles from the last 24 hours.
    - Keyword matching.
    - **Semantic Filtering**: Uses Google Gemini to select the most relevant and diverse stories based on your topics.
- **Script Generation**: Uses Gemini to write a professional, neutral news anchor script.
    - **Host & Reporter Mode**: Generates a dialogue between a Host (Arjav) and a Reporter (Arohi).
- **Audio Production**: Converts the script to speech using Google Cloud TTS with dynamic pacing and prosody (SSML).
    - **Multi-Voice**: Uses distinct WaveNet voices for the Host and Reporter.
- **Dual Schedule**: Automatically runs twice daily:
    - **Morning Briefing (6:30 AM PST)**: 15-minute deep dive.
    - **Evening Update (6:30 PM PST)**: 5-minute quick summary (labeled as "Quick News Briefing").
- **Auto-Cleanup**: Episodes older than 7 days are automatically deleted to keep the feed fresh.
- **Episode Links Page**: Generates a dedicated HTML page for each episode listing all source articles used.
- **Podcast Website**: Professional landing page at [https://amullick-git.github.io/news_bot/](https://amullick-git.github.io/news_bot/) with subscribe instructions and links to recent episode sources.

## Prerequisites

- Python 3.8+
- A Google Cloud Project with:
    - Gemini API enabled.
    - Cloud Text-to-Speech API enabled.
- A Service Account key for Cloud TTS.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/amullick-git/news_bot.git
    cd news_podcast
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **API Keys:**
    - Set your Google Gemini API key as an environment variable:
      ```bash
      export GOOGLE_API_KEY="your_gemini_api_key"
      ```
    - Set your Google Cloud Application Credentials:
      ```bash
      export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"
      ```

2.  **Customize Sources & Topics:**
    - Open `src/podcast_bot.py`.
    - Modify `RSS_SOURCES` to add/remove feeds.
    - Update `KEYWORDS` to change the topics you are interested in.

## Usage

Run the bot:

```bash
# Default (15 minutes)
python src/podcast_bot.py

# Custom duration (e.g., 5 minutes)
python src/podcast_bot.py --duration 5

# Test mode (saves to test_episodes/, no RSS update)
python src/podcast_bot.py --test


```

The script will:
1.  Fetch and filter news.
2.  Generate a source list (`episodes/episode_sources_YYYY-MM-DD_HH.md`).
3.  Generate a raw and cleaned script (`episodes/episode_script_raw.txt`, `episodes/episode_script_clean.txt`).
4.  Produce the final audio file (`episodes/episode_YYYY-MM-DD_HH.mp3`).

## Output

- **Audio**: `episodes/episode_YYYY-MM-DD_HH.mp3` - The final podcast episode.
- **Sources**: `episodes/episode_sources_YYYY-MM-DD_HH.md` - List of articles used (Markdown).
- **Links Page**: `episodes/links_YYYY-MM-DD_HH.html` - List of articles used (HTML webpage).
- **Scripts**: Text files containing the generated script.
- **RSS Feed**: `feed.xml` - The podcast feed file.

## Publishing to Podcast Apps

To make this podcast available on apps like Apple Podcasts, Spotify, or Pocket Casts, you need to host the `feed.xml` and MP3 files publicly.

### Step 1: Host on GitHub Pages

1.  Create a **public** GitHub repository for this project.
2.  Push all files (including `feed.xml` and `episode_*.mp3`) to the repository.
3.  Go to **Settings** > **Pages**.
4.  Under **Source**, select `main` branch (or `master`) and `/ (root)` folder.
5.  Click **Save**. GitHub will provide you a URL like `https://amullick-git.github.io/news_bot/`.
6.  **Important**: Ensure a `.nojekyll` file exists in your repo to allow serving of all files.

### Step 2: Update Configuration

1.  Open `src/podcast_bot.py`.
2.  Update `BASE_URL` with your GitHub Pages URL (e.g., `https://amullick-git.github.io/news_bot`).
3.  Run the bot again to regenerate `feed.xml` with the correct URLs:
    ```bash
    python src/podcast_bot.py
    ```
4.  Commit and push the updated `feed.xml`:
    ```bash
    git add feed.xml episode_*.mp3
    git commit -m "Update RSS feed and add new episode"
    git push
    ```

### Step 3: Subscribe

- **Direct URL**: You can now paste your feed URL (e.g., `https://amullick-git.github.io/news_bot/feed.xml`) directly into most podcast apps.
- **Submit to Directories**: You can submit this RSS feed URL to Apple Podcasts Connect, Spotify for Podcasters, etc.

### Styled RSS Feed

The RSS feed includes an XSLT stylesheet (`rss_style.xsl`) that renders the XML as a user-friendly webpage when viewed in a browser. This allows you to listen to episodes directly from the feed URL.

## Automation (GitHub Actions)

This repository includes a GitHub Actions workflow (`.github/workflows/daily_podcast.yml`) to generate the podcast automatically twice a day:
- **06:30 AM PST** (14:30 UTC): 15-minute episode.
- **06:30 PM PST** (02:30 UTC): 5-minute episode.

### Setup Secrets

For the automation to work, you must add your API keys to the GitHub Repository Secrets:

1.  **Get your Service Account Key (Base64)**:
    - Locate your Google Cloud Service Account JSON key file on your computer.
    - Convert it to a base64 string.
    - **Mac/Linux**: Run `base64 -i path/to/your/key.json | pbcopy` (this copies it to clipboard).
    - **Windows**: Use PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("path\to\key.json"))`

2.  **Add Secrets to GitHub**:
    - Go to your repository on GitHub.
    - Navigate to **Settings** > **Secrets and variables** > **Actions**.
    - Click **New repository secret**.
    - Add the following two secrets:
        - `GOOGLE_API_KEY`: Your Gemini API key.
        - `GCP_SA_KEY`: The **Base64 encoded string** you generated in step 1.

### Manual Trigger

You can also run the bot manually from GitHub:
1.  Go to the **Actions** tab.
2.  Select **Daily Podcast Generation**.
3.  Click **Run workflow**.

### Manual Trigger (Remote)
You can trigger the workflow remotely using the GitHub API or CLI.

**Using GitHub CLI:**
```bash
gh workflow run daily_podcast.yml -f duration=5
```

**Using cURL:**
```bash
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/amullick-git/news_bot/actions/workflows/daily_podcast.yml/dispatches \
  -d '{"ref":"main", "inputs": {"duration": "5"}}'
```

## Testing

To run the unit test suite:

```bash
python3 -m pytest tests/
```

The test suite covers:
- **Unit Tests**: `tests/test_podcast_bot.py` (Text processing, Date parsing, Webpage generation).
- **E2E Tests**: `tests/test_e2e.py` (Full pipeline simulation).

### Continuous Integration

A CI pipeline (`.github/workflows/ci.yml`) is configured to run these tests automatically on every push and pull request to the `main` branch. This ensures that new changes do not break existing functionality.

