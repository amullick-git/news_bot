import pytest
import os
import yaml
from src.config import load_config, Config

@pytest.fixture
def voice_config(tmp_path):
    """Creates a config file with sparse overrides for testing inheritance."""
    config_data = {
        "feeds": {"general": []},
        "keywords": {"general": []},
        "processing": {
            "duration_minutes": 10,
            "words_per_min": 150,
            "max_per_feed": 5,
            "max_final_articles": 10,
            "retention_days": 7,
            "voice_type": "wavenet" # Global default
        },
        "processing_overrides": {
            "daily": {
                "voice_type": "chirp3-hd" # Override only
            },
            "tech": {
                 # Empty override, should inherit wavenet
            },
            "kids": {
                "voice_type": "neural",
                "duration_minutes": 5
            }
        },
        "podcast": {
            "base_url": "http://test",
            "title": "Test",
            "author": "Test",
            "image_filename": "test.jpg",
            "language": "en",
            "episodes_dir": "episodes"
        }
    }
    
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return str(config_file)

def test_config_voice_inheritance(voice_config):
    """Test that overrides correctly inherit defaults and apply changes."""
    config = load_config(voice_config)
    
    # 1. Check Global Default
    assert config.processing.voice_type == "wavenet"
    
    # 2. Check "daily" override (sparse)
    # Should inherit duration=10 from default, but override voice
    daily = config.processing_overrides["daily"]
    assert daily.voice_type == "chirp3-hd"
    assert daily.duration_minutes == 10 
    
    # 3. Check "tech" override (empty/none in yaml, but effectively empty dict)
    # Should inherit everything including voice=wavenet
    tech = config.processing_overrides["tech"]
    assert tech.voice_type == "wavenet"
    
    # 4. Check "kids" override (mixed)
    kids = config.processing_overrides["kids"]
    assert kids.voice_type == "neural"
    assert kids.duration_minutes == 5
