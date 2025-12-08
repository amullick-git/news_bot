import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import shutil
import json

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import main as src_main
from src import fetcher

@pytest.fixture
def setup_e2e_env(tmp_path):
    """
    Sets up a temporary environment for E2E testing.
    Changes CWD to tmp_path and creates necessary files.
    """
    original_cwd = os.getcwd()
    
    # Change to temp directory
    os.chdir(tmp_path)
    
    # Create necessary files/dirs for new docs/ structure
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    episodes_dir = docs_dir / "episodes"
    episodes_dir.mkdir()
    
    # Create a minimal config.yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
podcast:
  base_url: "http://test.com"
  title: "Test Podcast"
  author: "Test Author"
  image_filename: "test.jpg"
  language: "en"
  episodes_dir: "docs/episodes"

feeds:
  general:
    - "http://example.com/rss"

keywords:
  general:
    - "news"
  kids:
    - "science"

processing:
  max_per_feed: 10
  max_final_articles: 5
  duration_minutes: 5
  words_per_min: 150
  gemini_model: "gemini-2.5-flash"
  retention_days: 7
""")
    
    # Create dummy index.html for the update logic (in docs/ now)
    index_file = docs_dir / "index.html"
    index_file.write_text("""
<!DOCTYPE html>
<html>
<body>
    <div class="container">
        <div class="links-list" id="episode-links-list">
            <!-- LINKS_INSERTION_POINT -->
        </div>
    </div>
</body>
</html>
""")
    
    yield tmp_path, episodes_dir
    
    # Cleanup
    os.chdir(original_cwd)

@patch('sys.argv', ['src/main.py', '--duration', '5']) # Removed --test to trigger full flow
@patch('src.audio.texttospeech.TextToSpeechClient')
@patch('src.content.genai.GenerativeModel')
@patch('src.main.fetch_all')
@patch('src.local_ai.LocalFilter.filter_by_relevance')
def test_full_flow_with_webpage_update(mock_filter, mock_fetch, mock_genai_model, mock_tts_client, setup_e2e_env):
    tmp_path, episodes_dir = setup_e2e_env
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    published_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # 1. Mock RSS Data
    items = [
        {
            "title": "Test News 1", 
            "summary": "Summary 1", 
            "link": "http://test.com/1", 
            "published": published_str
        },
        {
            "title": "Test News 2", 
            "summary": "Summary 2", 
            "link": "http://test.com/2", 
            "published": published_str
        },
    ]
    mock_fetch.return_value = items
    
    # 2. Mock Local Filter (Stage 1: Pass-through)
    mock_filter.return_value = items

    # 3. Mock Gemini Response
    mock_model_instance = MagicMock()
    mock_genai_model.return_value = mock_model_instance
    
    # Stage 2: Gemini filtering response (filter_by_semantics)
    mock_response_filtering = MagicMock()
    mock_response_filtering.text = "[0, 1]"  # Return indices of both items
    
    # Stage 3: Script Generation
    mock_response_script = MagicMock()
    mock_response_script.text = """
HOST: Welcome.
REPORTER: News 1.
HOST: Thanks.
"""
    
    # Two Gemini calls now: filtering + script generation
    mock_model_instance.generate_content.side_effect = [mock_response_filtering, mock_response_script]

    # 4. Mock TTS Response
    mock_client_instance = MagicMock()
    mock_tts_client.return_value = mock_client_instance
    mock_audio_resp = MagicMock()
    mock_audio_resp.audio_content = b"fake_audio_data"
    mock_client_instance.synthesize_speech.return_value = mock_audio_resp

    # 5. Run Main
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake_key"}):
        src_main.main()

    # 6. Verify Artifacts
    
    # Check for MP3
    mp3_files = list(episodes_dir.glob("*.mp3"))
    assert len(mp3_files) > 0, "No MP3 file created"
    today = datetime.now().strftime("%Y-%m-%d_%H")
    
    # Expect filenames to include the type (daily)
    # Note: args.type default is "daily" in test
    expected_mp3 = f"episode_daily_{today}.mp3" 
    expected_links = f"links_daily_{today}.html"
    
    assert os.path.exists(os.path.join(episodes_dir, expected_mp3))
    assert os.path.exists(os.path.join(tmp_path, "docs", "feed.xml"))
    assert os.path.exists(os.path.join(episodes_dir, expected_links))
    
    # Check for script
    assert (episodes_dir / "episode_script_clean.txt").exists()
    
    # Check for metadata
    json_files = list(episodes_dir.glob("episode_metadata_*.json"))
    assert len(json_files) > 0, "No metadata file created"
    
    # Check index.html updated (NEW) - now in docs/
    index_content = (tmp_path / "docs" / "index.html").read_text()
    # Check RSS Feed (now in docs/)
    feed_content = (tmp_path / "docs" / "feed.xml").read_text()
    # New Format: Title - Month Day, Year - HH AM/PM
    # e.g., "News Briefing - December 06, 2025 - 02 PM"
    # We check for the prefix and part of date/time
    assert "News Briefing (WaveNet) -" in feed_content
    # Ideally verify date is present, but regex matching for "Month" is simpler
    import re
    assert re.search(r"News Briefing \(WaveNet\) - [A-Z][a-z]+ \d{2}, \d{4} - \d{2} [AP]M", feed_content)
    assert "View Sources" in index_content
    
    # Check RSS Feed (NEW - since we removed --test)
    assert (tmp_path / "docs" / "feed.xml").exists(), "feed.xml not created"
    
    # Verify mocks
    mock_fetch.assert_called_once()
    mock_model_instance.generate_content.assert_called()
    mock_client_instance.synthesize_speech.assert_called()
