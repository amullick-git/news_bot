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
    # Interleave items for diversity? Or just append?
    # Appending is safer to preserve some implicit time ordering if we re-sort later.
    # But usually feeds are individually time-sorted.
    for domain, source_items in by_source.items():
        # Keep top N
        kept = source_items[:max_per_source]
        final_items.extend(kept)
        if len(source_items) > max_per_source:
             logger.info(f"Capped {domain} from {len(source_items)} to {max_per_source} items")

    logger.info(f"Source limiting processed {len(items)} -> {len(final_items)} items")
    return final_items

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
