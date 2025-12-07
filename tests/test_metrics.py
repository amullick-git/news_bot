import os
import pytest
from src.metrics import MetricsLogger

def test_metrics_logger(tmp_path):
    # Setup mock items
    fetched = [
        {"link": "https://bbc.com/1", "source_name": "BBC"},
        {"link": "https://bbc.com/2", "source_name": "BBC"},
        {"link": "https://nyt.com/1", "source_name": "NYT"},
        {"link": "https://unknown.com/1"} 
    ]
    
    shortlisted = [
        {"link": "https://bbc.com/1", "source_name": "BBC"},
        {"link": "https://nyt.com/1", "source_name": "NYT"},
    ]
    
    # Test Test Mode
    base_dir = str(tmp_path)
    logger = MetricsLogger(base_dir)
    
    logger.log_run(fetched, shortlisted, run_type="unit_test", is_test=True)
    
    test_file = os.path.join(base_dir, "metrics_test.md")
    assert os.path.exists(test_file)
    
    with open(test_file) as f:
        content = f.read()
        print(content)
        assert "## Run:" in content
        assert "Type: unit_test" in content
        assert "**Total Fetched**: 4 -> **Final Selection**: 2" in content
        assert "| BBC | 2 | 0 | 1 |" in content
        assert "| NYT | 1 | 0 | 1 |" in content
        assert "| unknown.com | 1 | 0 | 0 |" in content

    # Test with Stage 1 items
    stage1_items = [
        {"link": "https://bbc.com/1", "source_name": "BBC"},
        {"link": "https://bbc.com/2", "source_name": "BBC"},
        {"link": "https://nyt.com/1", "source_name": "NYT"}
    ]
    
    logger.log_run(fetched, shortlisted, run_type="stage1_test", is_test=True, local_ai_items=stage1_items)
    with open(test_file) as f:
        content = f.read()
        assert "**Total Fetched**: 4 -> **Stage 1 (Local AI)**: 3 -> **Stage 2 (Gemini Final)**: 2" in content

    # Test TTS Stats
    tts_stats = {"model": "test_model", "chars": 1234}
    logger.log_run(fetched, shortlisted, run_type="tts_test", is_test=True, tts_stats=tts_stats)
    
    with open(test_file) as f:
        content = f.read()
        assert "**TTS Usage**: 1234 chars (Model: test_model)" in content
        
    # Test Persistence (mocking persistence by using prod mode logic in a temp dir)
    # log_run only updates persistence if is_test=False
    logger.log_run(fetched, shortlisted, run_type="prod_tts", is_test=False, tts_stats=tts_stats)
    
    stats_file = os.path.join(base_dir, "metrics_stats.json")
    assert os.path.exists(stats_file)
    import json
    with open(stats_file) as f:
        data = json.load(f)
        assert data["tts_usage"]["test_model"] == 1234
        
    # Run again to test accumulation
    logger.log_run(fetched, shortlisted, run_type="prod_tts_2", is_test=False, tts_stats=tts_stats)
    with open(stats_file) as f:
        data = json.load(f)
        assert data["tts_usage"]["test_model"] == 2468

    # Test Prod Mode with Link
    logger.log_run(fetched, shortlisted, run_type="prod_run", is_test=False, links_file="links_prod.html")
    prod_file = os.path.join(base_dir, "metrics_prod.md")
    assert os.path.exists(prod_file)
    with open(prod_file) as f:
        content = f.read()
        assert "**Links File**: [links_prod.html](episodes/links_prod.html)" in content
