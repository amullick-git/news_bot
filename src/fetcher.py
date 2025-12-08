"""
RSS Fetcher & Filter
====================

This module is responsible for fetching news articles from RSS feeds and filtering them.
Key functionalities:
- Fetching feeds using `feedparser`.
- Filtering articles by time window (e.g., last 24 hours, last 7 days).
- Filtering articles by keywords.
- Parsing and normalizing dates.
"""
import feedparser
from datetime import datetime, timedelta
import email.utils as email_date_parser
from urllib.parse import urlparse
from typing import List, Dict, Any
from .utils import get_logger

logger = get_logger(__name__)

def parse_published_date(published_str: str) -> datetime:
    """
    Convert RSS published date string → datetime in UTC.
    If parsing fails, return None.
    """
    try:
        dt = email_date_parser.parsedate_to_datetime(published_str)
        # Some feeds return non-timezone-aware datetimes
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return dt
    except Exception:
        return None

def clean_source_name(title: str) -> str:
    """
    Cleans up RSS feed titles to get a friendly source name.
    e.g. "NYT > Technology" -> "NYT"
    """
    if not title or title.lower() in ["unknown title", "rss", "feed", "home"]:
        return None
        
    # 1. Split by common separators and take the first part
    separators = [' > ', ' - ', ' | ', ': ', ' – ']
    for sep in separators:
        if sep in title:
            title = title.split(sep)[0]
            
    # 2. Specific fixes for known messy feeds (optional but helpful)
    if "Search Records Found" in title:
        title = title.split(" Search Records")[0]
        
    return title.strip()

def fetch_feed(url: str, max_items: int = 10) -> List[Dict[str, Any]]:
    logger.info(f"Fetching feed: {url}")
    try:
        feed = feedparser.parse(url)
        
        # Extract and clean source name
        raw_title = feed.feed.get('title', '')
        source_name = clean_source_name(raw_title)
        
        items = []
        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title"),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "link": entry.get("link"),
                "source_name": source_name # Store the discovered name
            })
        return items
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return []

def fetch_all(sources: List[str], max_per_feed: int) -> List[Dict[str, Any]]:
    all_items = []
    for url in sources:
        items = fetch_feed(url, max_items=max_per_feed)
        all_items.extend(items)
    return all_items

def filter_by_time_window(items: List[Dict[str, Any]], hours: int = 24) -> List[Dict[str, Any]]:
    """
    Keep only stories published in the last N hours.
    """
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    cutoff = now - timedelta(hours=hours)

    filtered = []
    for item in items:
        published = item.get("published")
        if not published:
            continue

        dt = parse_published_date(published)
        if not dt:
            continue

        if dt >= cutoff:
            filtered.append(item)

    logger.info(f"Filtered {len(items)} -> {len(filtered)} items (last {hours}h)")
    return filtered

def filter_by_keywords(items: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return items
        
    out = []
    key_low = [k.lower() for k in keywords]
    for it in items:
        block = (it.get("title", "") + " " + it.get("summary", "")).lower()
        if any(k in block for k in key_low):
            out.append(it)
            
    logger.info(f"Filtered {len(items)} -> {len(out)} items (keywords)")
    return out

def limit_by_source(items: List[Dict[str, Any]], max_per_source: int) -> List[Dict[str, Any]]:
    """
    Groups items by source (netloc) and keeps only top N items per source.
    """
    if max_per_source <= 0:
        return items

    by_source = {}
    for item in items:
        link = item.get("link", "")
        # Extract domain as key (e.g. 'bbc.co.uk')
        try:
            domain = urlparse(link).netloc
        except:
            domain = "unknown"
            
        if domain not in by_source:
            by_source[domain] = []
        by_source[domain].append(item)

    final_items = []
    for domain, source_items in by_source.items():
        # Keep top N
        kept = source_items[:max_per_source]
        final_items.extend(kept)
        if len(source_items) > max_per_source:
             logger.info(f"Capped {domain} from {len(source_items)} to {max_per_source} items")

    logger.info(f"Source limiting processed {len(items)} -> {len(final_items)} items")
    return final_items

def get_friendly_source_names(sources_or_items: List[Any], limit: int = 6, randomize: bool = False) -> str:
    """
    Derive friendly names. 
    PRIORITY:
    1. 'source_name' field in item (from RSS metadata)
    2. Fallback to domain parsing
    """
    names = set()
    
    # 1. Try to extract from items
    for x in sources_or_items:
        if isinstance(x, dict):
            # If we have a good source name from the feed, use it
            if x.get("source_name"):
                names.add(x["source_name"])
                continue
                
            # Fallback: Parse URL
            url = x.get("link", "")
        else:
            url = str(x)
            
        # 2. Domain fallback (removed hardcoded map, using generic formatting)
        try:
            # e.g. "www.bbc.co.uk" -> "Bbc" ... slightly imperfect but a safety net
            # Improve: "news.ycombinator.com" -> "Hacker News" ? 
            # We keep a tiny hardcoded list for popular tech/news sites if metadata fails?
            
            # Simple Domain Formatter
            # "techcrunch.com" -> "Techcrunch"
            netloc = urlparse(url).netloc.replace("www.", "")
            name_part = netloc.split(".")[0].title()
            
            # Manual overrides just for when metadata fails entirely (e.g. Bloomberg)
            if "bloomberg" in netloc: name_part = "Bloomberg"
            elif "nytimes" in netloc: name_part = "NYT"
            elif "bbci" in netloc or "bbc." in netloc: name_part = "BBC"
            
            names.add(name_part)
        except: 
            pass
            
    sorted_names = sorted(list(names))
    
    # Cap the list
    if randomize and len(sorted_names) > limit:
        import random
        display_names = sorted(random.sample(sorted_names, limit))
        return ", ".join(display_names) + ", and others"
    elif len(sorted_names) > limit:
        display_names = sorted_names[:limit]
        return ", ".join(display_names) + ", and others"
    
    return ", ".join(sorted_names)
