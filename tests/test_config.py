import pytest
import os
import yaml
from src.config import load_config, Config

def test_load_config(tmp_path):
    config_data = {
        "feeds": {
            "general": ["http://example.com/rss"]
        },
        "keywords": {
            "general": ["test"]
        },
        "processing": {
            "duration_minutes": 10,
            "words_per_min": 100,
            "max_per_feed": 5,
            "max_final_articles": 5,
            "retention_days": 3,
            "gemini_model": "gemini-2.5-flash"
        },
        "podcast": {
            "base_url": "http://example.com",
            "title": "Test Podcast",
            "author": "Tester",
            "image_filename": "cover.jpg",
            "language": "en",
            "episodes_dir": "episodes"
        }
    }
    
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    config = load_config(str(config_file))
    
    assert config.feeds["general"] == ["http://example.com/rss"]
    assert config.processing.duration_minutes == 10
    assert config.podcast.title == "Test Podcast"
    assert config.podcast.image_url == "http://example.com/cover.jpg"
