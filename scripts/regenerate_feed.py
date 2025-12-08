#!/usr/bin/env python3
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__))))

from src.rss import generate_rss_feed, update_index_with_links
from src.config import load_config
from src.utils import setup_logging, get_logger

def main():
    setup_logging()
    logger = get_logger("regenerate_feed")
    logger.info("Regenerating RSS feed...")
    
    try:
        config = load_config()
        # Generate feed in docs/ directory (production structure)
        generate_rss_feed(config, output_dir="docs")
        
        # Update index.html
        update_index_with_links(config.podcast.episodes_dir, index_path="docs/index.html")
        
        logger.info("Feed regeneration complete.")
    except Exception as e:
        logger.error(f"Failed to regenerate feed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
