import pytest
import os
import yaml
from src.config import load_config, Config

def test_load_config(tmp_path):
    config_data = {
        "feeds": {
            "general": [
                "http://example.com/rss",
                {"url": "http://example.com/cricinfo", "limit": 2}
            ],
            "kids": ["http://example.com/rss"]
        },
        "keywords": {
            "general": ["test"],
            "kids": ["test"]
        },
        "processing": {
            "duration_minutes": 10,
            "words_per_min": 150,
            "max_per_feed": 5,
            "max_final_articles": 10,
            "retention_days": 7,
            "gemini_model": "gemini-1.5-flash"
        },
        "processing_overrides": {
            "kids": {
                "duration_minutes": 5,
                "words_per_min": 100,
                "max_per_feed": 3,
                "max_final_articles": 5,
                "retention_days": 7,
                "gemini_model": "gemini-1.5-flash"
            }
        },
        "podcast": {
            "base_url": "http://example.com",
            "title": "Test Podcast",
            "author": "Test Author",
            "image_filename": "cover.jpg",
            "language": "en",
            "episodes_dir": "episodes"
        }
    }
    
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    config = load_config(str(config_file))
    
    assert config.feeds["general"] == ["http://example.com/rss", "http://example.com/cricinfo"]
    assert config.source_limits["example.com"] == 2
    assert config.processing.duration_minutes == 10
    
    # Test overrides
    assert config.processing_overrides is not None
    assert "kids" in config.processing_overrides
    assert config.processing_overrides["kids"].duration_minutes == 5
    assert config.processing.gemini_filter_model == "gemini-2.5-flash-lite" # Default check
    assert config.podcast.title == "Test Podcast"
    assert config.podcast.image_url == "http://example.com/cover.jpg"
