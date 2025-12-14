import os
import json
import pytest
from datetime import datetime, timedelta
from src import archive

@pytest.fixture
def temp_archive_dir(tmp_path):
    return str(tmp_path / "archive_test")

def test_save_items(temp_archive_dir):
    items = [{"title": "News A", "link": "http://a.com"}]
    
    filepath = archive.save_items(items, temp_archive_dir)
    
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        saved = json.load(f)
    assert len(saved) == 1
    assert saved[0]["title"] == "News A"

def test_save_items_deduplicate(temp_archive_dir):
    items = [{"title": "News A", "link": "http://a.com"}]
    
    # Save once
    archive.save_items(items, temp_archive_dir)
    
    # Save again with same item + new item
    items_new = [
        {"title": "News A", "link": "http://a.com"}, # Duplicate
        {"title": "News B", "link": "http://b.com"}
    ]
    filepath = archive.save_items(items_new, temp_archive_dir)
    
    with open(filepath, "r") as f:
        saved = json.load(f)
        
    # Should merge, keeping unique by link
    assert len(saved) == 2
    titles = {x["title"] for x in saved}
    assert "News A" in titles
    assert "News B" in titles

def test_load_items_lookback(temp_archive_dir):
    # Setup: Create fake archive files for last 3 days
    today = datetime.now()
    
    data_map = {}
    
    # Day 0 (Today)
    f0 = archive.get_archive_path(temp_archive_dir, today)
    data0 = [{"title": "Today News", "link": "link0"}]
    data_map[0] = data0
    
    # Day 1 (Yesterday)
    f1 = archive.get_archive_path(temp_archive_dir, today - timedelta(days=1))
    data1 = [{"title": "Yesterday News", "link": "link1"}]
    data_map[1] = data1
    
    # Day 5 (Old)
    f5 = archive.get_archive_path(temp_archive_dir, today - timedelta(days=5))
    data5 = [{"title": "Old News", "link": "link5"}]
    data_map[5] = data5
    
    os.makedirs(temp_archive_dir, exist_ok=True)
    for f, d in [(f0, data0), (f1, data1), (f5, data5)]:
        with open(f, "w") as file:
            json.dump(d, file)
            
    # Act: Load with lookback=2 (Should get Day 0 and Day 1, but NOT Day 5)
    loaded = archive.load_items(temp_archive_dir, lookback_days=2)
    
    titles = {x["title"] for x in loaded}
    assert "Today News" in titles
    assert "Yesterday News" in titles
    assert "Old News" not in titles

def test_cleanup_archive(temp_archive_dir):
    today = datetime.now()
    retention = 7
    
    # Recent file (within retention)
    f_recent = archive.get_archive_path(temp_archive_dir, today - timedelta(days=2))
    
    # Old file (outside retention)
    f_old = archive.get_archive_path(temp_archive_dir, today - timedelta(days=retention + 5))
    
    os.makedirs(temp_archive_dir, exist_ok=True)
    
    with open(f_recent, "w") as f: json.dump([], f)
    with open(f_old, "w") as f: json.dump([], f)
    
    # Act
    archive.cleanup_archive(temp_archive_dir, retention_days=retention)
    
    # Assert
    assert os.path.exists(f_recent)
    assert not os.path.exists(f_old)

def test_save_load_with_tag(temp_archive_dir):
    items = [{"title": "Tech News", "link": "http://tech.com"}]
    tag = "tech"
    today = datetime.now()
    
    # Save with tag
    filepath = archive.save_items(items, temp_archive_dir, tag=tag)
    
    # Verify filename contains tag
    assert f"_{tag}.json" in filepath
    assert os.path.exists(filepath)
    
    # Load with tag should find it
    loaded = archive.load_items(temp_archive_dir, lookback_days=1, tag=tag)
    assert len(loaded) == 1
    assert loaded[0]["title"] == "Tech News"
    
    # Load with different tag should NOT find it
    loaded_other = archive.load_items(temp_archive_dir, lookback_days=1, tag="other")
    assert len(loaded_other) == 0

def test_cleanup_includes_tagged(temp_archive_dir):
    today = datetime.now()
    retention = 7
    
    f_old_tagged = archive.get_archive_path(temp_archive_dir, today - timedelta(days=20), tag="kids")
    os.makedirs(temp_archive_dir, exist_ok=True)
    with open(f_old_tagged, "w") as f: json.dump([], f)
    
    assert os.path.exists(f_old_tagged)
    
    archive.cleanup_archive(temp_archive_dir, retention_days=retention)
    
    assert not os.path.exists(f_old_tagged)
