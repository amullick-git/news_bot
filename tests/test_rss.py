import os
import re
from datetime import datetime
from src.rss import generate_episode_links_page, update_index_with_links

def test_generate_episode_links_page_parsing(tmp_path):
    # Setup
    episodes_dir = str(tmp_path)
    items = [{"title": "News 1", "link": "https://example.com"}]
    
    # Run with complex timestamp (type_date)
    timestamp = "tech_daily_2025-01-01_10"
    filename = generate_episode_links_page(items, timestamp, episodes_dir)
    
    filepath = os.path.join(episodes_dir, filename)
    assert os.path.exists(filepath)
    
    with open(filepath, "r") as f:
        content = f.read()
        # Verify Title Parsing
        assert "Tech Daily: January 01, 2025 - 10 AM" in content
        assert "News 1" in content

def test_update_index_parsing(tmp_path, monkeypatch):
    # Setup index.html with placeholder
    index_path = str(tmp_path / "index.html")
    with open(index_path, "w") as f:
        f.write('<html><body><div class="links-list" id="episode-links-list"><!-- EPISODE_LIST_START --><!-- EPISODE_LIST_END --></div></body></html>')
        
    # Create fake link files
    # 1. New Format
    with open(str(tmp_path / "links_tech_daily_2025-01-01_10.html"), "w") as f: f.write("content")
    # 2. Legacy Format
    with open(str(tmp_path / "links_2024-01-01_10.html"), "w") as f: f.write("content")
    
    # Run update
    # Run update
    monkeypatch.chdir(tmp_path) # Ensure we work in tmp dir
    update_index_with_links(str(tmp_path))
    
    with open(index_path, "r") as f:
        content = f.read()
        print(content)
        
        # Verify New Format Label
        assert "[Tech Daily] January 01, 2025 - 10:00 AM" in content
        
        # Verify Legacy Label
        assert "January 01, 2024 - 10:00 AM" in content
        assert "[Legacy]" not in content # Should not have bracket prefix if no type

def test_rss_voice_suffix(tmp_path, monkeypatch):
    from src.rss import generate_rss_feed
    from src.config import Config, PodcastConfig, ProcessingConfig, NotificationConfig
    import json
    
    # Mock Config
    config = Config(
        feeds={}, keywords={},
        processing=ProcessingConfig(
            duration_minutes=10, words_per_min=100, max_per_feed=5, max_final_articles=5, retention_days=100
        ),
        podcast=PodcastConfig(
            base_url="http://test", title="Show", author="Me", 
            image_filename="img.jpg", language="en", episodes_dir=str(tmp_path / "episodes")
        ),
        notification=NotificationConfig(enabled=False)
    )
    
    ep_dir = tmp_path / "episodes"
    ep_dir.mkdir()
    
    # Create Episode + Metadata (Chirp)
    (ep_dir / "episode_daily_2025-01-01_10.mp3").write_text("audio")
    meta = {"type": "daily", "title_prefix": "Daily News", "voice_type": "chirp3-hd"}
    with open(ep_dir / "episode_metadata_daily_2025-01-01_10.json", "w") as f:
        json.dump(meta, f)
        
    # Create Episode + Metadata (Wavenet)
    (ep_dir / "episode_tech_2025-01-01_12.mp3").write_text("audio")
    meta2 = {"type": "tech", "title_prefix": "Tech News", "voice_type": "wavenet"}
    with open(ep_dir / "episode_metadata_tech_2025-01-01_12.json", "w") as f:
        json.dump(meta2, f)
        
    # Run
    # Run with explicit output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    monkeypatch.chdir(tmp_path)
    generate_rss_feed(config, output_dir=str(output_dir))
    
    # Check that feed.xml is in output_dir, NOT in root (which is tmp_path here)
    assert (output_dir / "feed.xml").exists()
    assert not (tmp_path / "feed.xml").exists()
    
    with open(output_dir / "feed.xml") as f:
        content = f.read()
        assert "Daily News (Chirp)" in content
        assert "Tech News Briefing (WaveNet)" in content

def test_update_index_relative_links(tmp_path):
    # Setup structure:
    # docs/index.html
    # docs/episodes/links_xxx.html
    
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    episodes_dir = docs_dir / "episodes"
    episodes_dir.mkdir()
    
    index_path = docs_dir / "index.html"
    index_path.write_text('<html><body><div class="links-list" id="episode-links-list"><!-- EPISODE_LIST_START --><!-- EPISODE_LIST_END --></div></body></html>')
    
    (episodes_dir / "links_test_2025-01-01_10.html").write_text("content")
    
    # Run update
    # Note: caller uses full paths usually
    update_index_with_links(str(episodes_dir), index_path=str(index_path))
    
    content = index_path.read_text()
    
    # Check for relative link
    # Should be "episodes/links_..."
    assert 'href="episodes/links_test_2025-01-01_10.html"' in content
    assert 'href="docs/episodes/' not in content

def test_update_index_with_mp3(tmp_path):
    # Setup structure:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    episodes_dir = docs_dir / "episodes"
    episodes_dir.mkdir()
    
    index_path = docs_dir / "index.html"
    index_path.write_text('<html><body><div class="links-list" id="episode-links-list"><!-- EPISODE_LIST_START --><!-- EPISODE_LIST_END --></div></body></html>')
    
    # HTML file
    (episodes_dir / "links_test_2025-01-01_10.html").write_text("content")
    # MP3 file
    (episodes_dir / "episode_test_2025-01-01_10.mp3").write_text("audio")
    
    # Run update
    from src.rss import update_index_with_links
    update_index_with_links(str(episodes_dir), index_path=str(index_path))
    
    content = index_path.read_text()
    
    # Check for MP3 link
    assert "Play MP3" in content
    assert 'href="episodes/episode_test_2025-01-01_10.mp3"' in content
