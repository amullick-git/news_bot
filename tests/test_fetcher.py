import pytest
from datetime import datetime, timedelta
from src.fetcher import filter_last_24_hours, filter_by_keywords

def test_filter_last_24_hours():
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    
    items = [
        {"title": "New", "published": now.strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "Old", "published": (now - timedelta(hours=25)).strftime("%a, %d %b %Y %H:%M:%S %z")},
        {"title": "No Date"}
    ]
    
    filtered = filter_last_24_hours(items)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "New"

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
