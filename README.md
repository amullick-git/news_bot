# News Podcast Generator

This project is an automated tool that fetches news from various RSS feeds, filters them based on keywords and semantic relevance using Google Gemini, generates a script, and converts it into a podcast-style audio file using Google Cloud Text-to-Speech.

## Features

- **RSS Feed Fetching**: Pulls news from BBC, NYT, NDTV, Hacker News, The Verge, CNBC, NPR, and more.
- **Smart Filtering**:
    - Filters articles from the last 24 hours.
    - Keyword matching.
    - **Semantic Filtering**: Uses Google Gemini to select the most relevant and diverse stories based on your topics.
- **Script Generation**: Uses Gemini to write a professional, neutral news anchor script.
- **Audio Production**: Converts the script to speech using Google Cloud TTS with dynamic pacing and prosody (SSML).

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
    - Open `podcast_bot.py`.
    - Modify `RSS_SOURCES` to add/remove feeds.
    - Update `KEYWORDS` to change the topics you are interested in.

## Usage

Run the bot:

```bash
python podcast_bot.py
```

The script will:
1.  Fetch and filter news.
2.  Generate a source list (`episode_sources_YYYY-MM-DD_HH.md`).
3.  Generate a raw and cleaned script (`episode_script_raw.txt`, `episode_script_clean.txt`).
4.  Produce the final audio file (`episode_YYYY-MM-DD_HH.mp3`).

## Output

- **Audio**: `episode_YYYY-MM-DD_HH.mp3` - The final podcast episode.
- **Sources**: `episode_sources_YYYY-MM-DD_HH.md` - List of articles used.
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

1.  Open `podcast_bot.py`.
2.  Update `BASE_URL` with your GitHub Pages URL (e.g., `https://amullick-git.github.io/news_bot`).
3.  Run the bot again to regenerate `feed.xml` with the correct URLs:
    ```bash
    python podcast_bot.py
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
