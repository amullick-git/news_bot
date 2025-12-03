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

def fetch_feed(url: str, max_items: int = 10) -> List[Dict[str, Any]]:
    logger.info(f"Fetching feed: {url}")
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title"),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "link": entry.get("link")
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

def filter_last_24_hours(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep only stories published in the last 24 hours.
    """
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    cutoff = now - timedelta(hours=24)

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

    logger.info(f"Filtered {len(items)} -> {len(filtered)} items (last 24h)")
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

def get_friendly_source_names(sources: List[str]) -> str:
    """
    Derive friendly names from RSS_SOURCES for the intro.
    """
    names = set()
    for url in sources:
        if "bbc" in url: names.add("BBC")
        elif "nytimes" in url: names.add("NYT")
        elif "ndtv" in url: names.add("NDTV")
        elif "hnrss" in url: names.add("Hacker News")
        elif "theverge" in url: names.add("The Verge")
        elif "cnbc" in url: names.add("CNBC")
        elif "npr" in url: names.add("NPR")
        else:
            # Fallback to domain
            try:
                domain = urlparse(url).netloc.replace("www.", "").split(".")[0].title()
                names.add(domain)
            except: pass
    return ", ".join(sorted(list(names)))
