import pytest
from src.local_ai import LocalFilter

# Mock items
MOCK_ITEMS = [
    {"title": "SpaceX Launch 1", "summary": "Rocket goes up.", "link": "https://spacex.com/1"},
    {"title": "SpaceX Launch 2", "summary": "Another rocket.", "link": "https://spacex.com/2"},
    {"title": "SpaceX Launch 3", "summary": "Yet another.", "link": "https://spacex.com/3"},
    {"title": "NASA Mars", "summary": "Red planet.", "link": "https://nasa.gov/1"},
    {"title": "Cookies", "summary": "Yummy food.", "link": "https://cooking.com/1"},
]

def test_local_filter_singleton():
    f1 = LocalFilter()
    f2 = LocalFilter()
    assert f1 is f2

def test_local_filter_relevance():
    f = LocalFilter()
    # Assuming model loads (it should in this env since we installed it)
    # If model fails to load, this test might skip or fail gracefully if we mocked the internal load
    
    # We can rely on the real model for this test as we know it's installed
    result = f.filter_by_relevance(
        items=MOCK_ITEMS, 
        topics=["Space Exploration"], 
        limit=5, 
        threshold=0.2
    )
    
    # Should keep Space stuff, drop Cookies
    titles = [i['title'] for i in result]
    assert "NASA Mars" in titles
    assert "SpaceX Launch 1" in titles
    assert "Cookies" not in titles

def test_local_filter_diversity():
    f = LocalFilter()
    
    # Test strict limit of 2 per source
    result = f.filter_by_relevance(
        items=MOCK_ITEMS, 
        topics=["Space Exploration"], 
        limit=5, 
        threshold=0.2,
        max_per_source=2
    )
    
    # Checks
    titles = [i['title'] for i in result]
    spacex_count = sum(1 for link in [i['link'] for i in result] if "spacex.com" in link)
    
    assert spacex_count <= 2
    assert "NASA Mars" in titles
