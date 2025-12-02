import pytest
import sys
import os
from datetime import datetime

# Add parent directory to path to import podcast_bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.podcast_bot import (
    strip_markdown_formatting,
    remove_stage_directions,
    ensure_sentence_punctuation,
    collapse_whitespace,
    parse_published_date
)

def test_strip_markdown_formatting():
    text = """
    # Headline
    **Bold text**
    * Bullet point
    1. Numbered list
    """
    cleaned = strip_markdown_formatting(text)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "1." not in cleaned
    assert "Headline" in cleaned
    assert "Bold text" in cleaned

def test_remove_stage_directions():
    text = """
    HOST: Hello world.
    (Music fades in)
    REPORTER: Here is the news.
    [Applause]
    *laughs*
    """
    cleaned = remove_stage_directions(text)
    assert "(Music fades in)" not in cleaned
    assert "[Applause]" not in cleaned
    assert "*laughs*" not in cleaned
    assert "HOST: Hello world." in cleaned

def test_ensure_sentence_punctuation():
    text = "This is a sentence\nThis is another one.\nShort"
    cleaned = ensure_sentence_punctuation(text)
    lines = cleaned.split('\n')
    assert lines[0].strip() == "This is a sentence."
    assert lines[1].strip() == "This is another one."
    assert lines[2].strip() == "Short" # Short lines skipped

def test_collapse_whitespace():
    text = "Line 1\n\n\nLine 2   with   spaces"
    cleaned = collapse_whitespace(text)
    assert "\n\n\n" not in cleaned
    assert cleaned == "Line 1\n\nLine 2 with spaces"

def test_parse_published_date():
    # Test RFC822 date
    rfc_date = "Sun, 30 Nov 2025 08:00:00 +0000"
    dt = parse_published_date(rfc_date)
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 11
    assert dt.day == 30

    # Test invalid date
    assert parse_published_date("Invalid Date") is None

# ==========================================
# Webpage Generation Tests
# ==========================================

import shutil
from datetime import timedelta
import re
from src import podcast_bot

@pytest.fixture
def setup_test_env(tmp_path):
    """
    Setup a temporary environment for testing.
    Override podcast_bot.EPISODES_DIR and change working directory.
    """
    # Save original values
    original_episodes_dir = podcast_bot.EPISODES_DIR
    original_cwd = os.getcwd()
    
    # Setup temp dirs
    test_episodes_dir = tmp_path / "episodes"
    test_episodes_dir.mkdir()
    
    # Override global variable
    podcast_bot.EPISODES_DIR = "episodes"
    
    # Change cwd to tmp_path so that "index.html" is looked up there
    os.chdir(tmp_path)
    
    yield tmp_path, test_episodes_dir
    
    # Teardown: restore
    podcast_bot.EPISODES_DIR = original_episodes_dir
    os.chdir(original_cwd)

def test_generate_episode_links_page(setup_test_env):
    _, episodes_dir = setup_test_env
    
    items = [
        {"title": "Story 1", "link": "https://example.com/1", "summary": "Sum 1"},
        {"title": "Story 2", "link": "https://test.org/2", "summary": "Sum 2"}
    ]
    timestamp = "2025-12-02_10"
    
    filename = podcast_bot.generate_episode_links_page(items, timestamp)
    
    expected_path = episodes_dir / f"links_{timestamp}.html"
    assert expected_path.exists()
    
    content = expected_path.read_text()
    assert "Story 1" in content
    assert "https://example.com/1" in content
    assert "Story 2" in content
    assert "Episode Sources: 2025-12-02 10" in content

def test_update_index_with_links(setup_test_env):
    root_dir, episodes_dir = setup_test_env
    
    # Create a dummy index.html
    index_html = root_dir / "index.html"
    index_html.write_text("""
    <html>
    <body>
        <div class="links-list" id="episode-links-list">
            <!-- LINKS_INSERTION_POINT -->
        </div>
    </body>
    </html>
    """)
    
    # Create some dummy link pages
    (episodes_dir / "links_2025-12-01_10.html").touch()
    (episodes_dir / "links_2025-12-02_10.html").touch()
    
    podcast_bot.update_index_with_links()
    
    updated_content = index_html.read_text()
    
    # Check if links are inserted
    assert 'href="episodes/links_2025-12-02_10.html"' in updated_content
    assert 'href="episodes/links_2025-12-01_10.html"' in updated_content
    
    # Check order (newest first) - simple string check might be enough if format is consistent
    pos_new = updated_content.find("links_2025-12-02_10.html")
    pos_old = updated_content.find("links_2025-12-01_10.html")
    assert pos_new < pos_old

def test_cleanup_old_episodes_links(setup_test_env):
    _, episodes_dir = setup_test_env
    
    # Create files
    # Old file (older than 7 days)
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    old_file = episodes_dir / f"links_{old_date}_10.html"
    old_file.touch()
    
    # New file (today)
    new_date = datetime.now().strftime("%Y-%m-%d")
    new_file = episodes_dir / f"links_{new_date}_10.html"
    new_file.touch()
    
    # Run cleanup
    podcast_bot.cleanup_old_episodes()
    
    assert not old_file.exists()
    assert new_file.exists()
