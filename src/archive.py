"""
Archive Manager
===============

Handles the persistence of fetched news articles to JSON files to build a local history.
This allows weekly runs to access articles seen in daily runs, even if they have fallen off RSS feeds.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .fetcher import parse_published_date

logger = logging.getLogger(__name__)

def get_archive_path(directory: str, date_object: datetime) -> str:
    """Returns the filename for a given date: data/archive/YYYY-MM-DD.json"""
    filename = date_object.strftime("%Y-%m-%d") + ".json"
    return os.path.join(directory, filename)

def save_items(items: List[Dict[str, Any]], directory: str) -> str:
    """
    Saves a list of items to a JSON archive file for the current date.
    Overwrite existing file for the day (or merge? likely overwrite is fine for a daily run).
    Returns the path to the saved file.
    """
    if not items:
        return None
        
    os.makedirs(directory, exist_ok=True)
    
    # Use today's date for the archive bucket
    today = datetime.now()
    filepath = get_archive_path(directory, today)
    
    try:
        # Load existing if any (to avoid overwriting if run multiple times a day)
        existing_items = []
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                try:
                    existing_items = json.load(f)
                except:
                    pass
        
        # Deduplicate Merge (Simple ID check if link exists)
        # We assume 'items' are fresh.
        seen_links = {x.get('link') for x in existing_items if x.get('link')}
        
        new_count = 0
        for item in items:
            if item.get('link') and item.get('link') not in seen_links:
                existing_items.append(item)
                seen_links.add(item.get('link'))
                new_count += 1
            
        with open(filepath, "w") as f:
            json.dump(existing_items, f, indent=2)
            
        logger.info(f"Archived {len(items)} items to {filepath} (New: {new_count}, Total in file: {len(existing_items)})")
        return filepath
    except Exception as e:
        logger.error(f"Failed to archive items: {e}")
        return None

def load_items(directory: str, lookback_days: int) -> List[Dict[str, Any]]:
    """
    Loads items from all archive files within the lookback window.
    Strictly adheres to the lookback period to avoid stale news.
    """
    if not os.path.exists(directory):
        logger.warning(f"Archive directory {directory} does not exist.")
        return []

    all_items = []
    
    # Calculate date window
    today = datetime.now()
    # If lookback is 7, we want today, yesterday... up to 7 days ago.
    
    loaded_files = 0
    
    # Iterate exactly the days in the window
    for i in range(lookback_days + 1):
        target_date = today - timedelta(days=i)
        filepath = get_archive_path(directory, target_date)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    day_items = json.load(f)
                    all_items.extend(day_items)
                    loaded_files += 1
            except Exception as e:
                logger.error(f"Error reading archive {filepath}: {e}")
        else:
             # It's expected some days might miss if not run
             pass
             
    logger.info(f"Loaded {len(all_items)} archived items from {loaded_files} files (last {lookback_days} days)")
    return all_items

def cleanup_archive(directory: str, retention_days: int) -> None:
    """
    Removes archive files older than retention_days.
    """
    if not os.path.exists(directory):
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    count = 0
    for filename in os.listdir(directory):
        if not filename.endswith(".json"):
            continue
            
        try:
            # Parse date from filename "YYYY-MM-DD.json"
            date_str = filename.replace(".json", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if file_date < cutoff_date:
                os.remove(os.path.join(directory, filename))
                count += 1
                logger.info(f"Removed old archive: {filename}")
        except ValueError:
            # Skip files that don't match the expected format
            continue
            
    if count > 0:
        logger.info(f"Cleaned up {count} old archive files.")
