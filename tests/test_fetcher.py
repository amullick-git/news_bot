import pytest
from datetime import datetime, timedelta
from src.fetcher import filter_by_time_window, filter_by_keywords, get_friendly_source_names

def test_filter_by_time_window():
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    
    items = [
        {"title": "New", "published": now.strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "Yesterday", "published": (now - timedelta(hours=23)).strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "Old", "published": (now - timedelta(hours=25)).strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "Week Old", "published": (now - timedelta(days=6)).strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "Ancient", "published": (now - timedelta(days=8)).strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "No Date"}
    ]
    
    # Test 24 hours (default)
    filtered_24h = filter_by_time_window(items, hours=24)
    assert len(filtered_24h) == 2
    titles_24h = [i["title"] for i in filtered_24h]
    assert "New" in titles_24h
    assert "Yesterday" in titles_24h
    
    # Test 7 days (168 hours)
    filtered_7d = filter_by_time_window(items, hours=168)
    assert len(filtered_7d) == 4
    titles_7d = [i["title"] for i in filtered_7d]
    assert "New" in titles_7d
    assert "Yesterday" in titles_7d
    assert "Old" in titles_7d
    assert "Week Old" in titles_7d
    assert "Ancient" not in titles_7d

def test_get_friendly_source_names():
    # Test with item dicts
    items = [
        {"link": "https://www.bbc.com/news/123"},
        {"link": "https://www.nytimes.com/tech/456"},
        {"link": "https://other-domain.com/article"},
        {"link": "https://www.theverge.com/2024/01/01/cool-gadget"}
    ]
    
    names_str = get_friendly_source_names(items)
    assert "BBC" in names_str
    assert "NYT" in names_str
    assert "The Verge" in names_str
    assert "Other-Domain" in names_str

    # Test Limiting to 2
    names_limited = get_friendly_source_names(items, limit=2)
    assert names_limited.count(",") >= 1 # At least one comma
    assert "and others" in names_limited

def test_filter_by_keywords():
    items = [
        {"title": "AI News", "summary": "Something about AI"},
        {"title": "Cooking", "summary": "Recipes"},
        {"title": "Tech", "summary": "New gadgets"}
    ]
    
    filtered = filter_by_keywords(items, ["ai", "tech"])
    assert len(filtered) == 2
    titles = [i["title"] for i in filtered]
    assert "AI News" in titles
    assert "Tech" in titles
    assert "Cooking" not in titles
