"""
Main Entry Point
================

This module serves as the primary entry point for the News Podcast Generator.
It orchestrates the entire pipeline, including:
1. Loading configuration.
2. Fetching and filtering news articles.
3. Generating scripts using LLM (Gemini).
4. Converting scripts to audio (TTS).
5. Updating the RSS feed and HTML pages.

Usage:
    python -m src.main [--duration MINS] [--test] [--lookback-days DAYS] [--type TYPE]
"""
import argparse
import os
import json
from datetime import datetime
from urllib.parse import urlparse

from .config import load_config
from .utils import setup_logging, get_logger
from .fetcher import fetch_all, filter_by_time_window, filter_by_keywords, get_friendly_source_names
from .content import configure_gemini, filter_by_semantics, summarize_with_gemini
from .audio import postprocess_for_tts_plain, text_to_speech
from .rss import generate_rss_feed, generate_episode_links_page, update_index_with_links, cleanup_old_episodes

logger = get_logger(__name__)

def write_episode_sources(items, filename):
    lines = []
    lines.append("# Episode Sources\n")
    for i, item in enumerate(items, 1):
        link = item.get("link", "")
        title = item.get("title", "Untitled")
        netloc = urlparse(link).netloc or "source"
        lines.append(f"{i}. **{title}**  \n   _{netloc}_  \n   {link}\n")

    content = "\n".join(lines)
    with open(filename, "w") as f:
        f.write(content)
    logger.info(f"Episode sources saved to {filename}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, help="Target duration in minutes")
    parser.add_argument("--test", action="store_true", help="Run in test mode (save to test_episodes/, no RSS update)")
    parser.add_argument("--lookback-days", type=int, default=1, help="Number of days to look back for news (default: 1)")
    parser.add_argument("--type", type=str, default="daily", help="Episode type: daily or weekly")
    parser.add_argument("--title-prefix", type=str, default="News Briefing", help="Prefix for the episode title")
    args = parser.parse_args()

    setup_logging()
    config = load_config()

    # Override config with args if provided
    if args.duration:
        config.processing.duration_minutes = args.duration
    
    if args.test:
        logger.info("TEST MODE ENABLED")
        config.podcast.episodes_dir = "test_episodes"
        logger.info(f"Output directory set to: {config.podcast.episodes_dir}")

    logger.info("=== Fetching news... ===")
    
    # Select feeds based on type
    # If type contains 'tech', use tech feeds. Otherwise use general.
    # Map specific types (tech_daily, tech_weekly) to 'tech'
    # Map 'kids_daily' to 'kids'
    # Map others (morning, evening, weekly) to 'general'
    if "tech" in args.type:
        feed_key = "tech"
    elif "kids" in args.type:
        feed_key = "kids"
    else:
        feed_key = "general"
        
    # Apply processing overrides if defined for this category
    if config.processing_overrides and feed_key in config.processing_overrides:
        logger.info(f"Applying processing overrides for category: {feed_key}")
        config.processing = config.processing_overrides[feed_key]
        # Re-apply CLI duration override if provided, as it should take precedence
        if args.duration:
            config.processing.duration_minutes = args.duration

    selected_feeds = config.feeds.get(feed_key, config.feeds["general"])
    
    logger.info(f"Selected feed category: {feed_key} ({len(selected_feeds)} feeds)")
    
    # FETCH STEP: Use deep fetch limit (e.g. 100) to ensure history coverage
    fetch_limit = getattr(config.processing, "fetch_limit", 100)
    items = fetch_all(selected_feeds, fetch_limit)

    lookback_hours = args.lookback_days * 24
    items = filter_by_time_window(items, hours=lookback_hours)

    configure_gemini(api_key=os.getenv("GOOGLE_API_KEY"))

    # Select keywords based on type, similar to feeds
    # Re-using feed_key logic is safe here as structure mirrors feeds
    kw_key = feed_key # "tech", "kids", or "general"
    selected_keywords = config.keywords.get(kw_key, config.keywords["general"])

    # KEYWORD FILTER STEP: Reduce noise before AI
    if selected_keywords:
        logger.info(f"Filtering by keywords (Text Match): {selected_keywords}")
        items = filter_by_keywords(items, selected_keywords)

    # SOURCE LIMIT STEP: Soft cap to ensure diversity (e.g. top 25 per source)
    # This prevents one busy feed from dominating history
    # 'max_per_feed' is now serving as this diversity cap
    from .fetcher import limit_by_source
    items = limit_by_source(items, config.processing.max_per_feed)

    if not items:
        logger.warning("No articles found after filtering.")
        return

    # SEMANTIC FILTER STEP: AI Selection
    if selected_keywords:
        logger.info(f"Filtering by semantics (Gemini) for topics: {selected_keywords}")
        items = filter_by_semantics(items, selected_keywords, config.processing.gemini_model, limit=config.processing.max_final_articles)

    items = items[:config.processing.max_final_articles]

    if not items:
        logger.warning("No articles found. Try different keywords.")
        return

    logger.info(f"Using {len(items)} stories")
    
    os.makedirs(config.podcast.episodes_dir, exist_ok=True)

    target_words = config.processing.words_per_min * config.processing.duration_minutes
    logger.info(f"Target duration: {config.processing.duration_minutes} minutes (~{target_words} words)")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    filename_suffix = f"{args.type}_{timestamp}"

    sources_file = os.path.join(config.podcast.episodes_dir, f"episode_sources_{filename_suffix}.md")
    write_episode_sources(items, sources_file)

    friendly_sources = get_friendly_source_names(items, limit=6)
    
    # Determine audience
    audience = "kids" if "kids" in args.type else "general"
    
    script = summarize_with_gemini(items, target_words, config.processing.gemini_model, friendly_sources, audience=audience)

    raw_script_path = os.path.join(config.podcast.episodes_dir, "episode_script_raw.txt")
    with open(raw_script_path, "w") as f:
        f.write(script)
    logger.info(f"Raw script saved to {raw_script_path}")

    clean_script = postprocess_for_tts_plain(script)

    clean_script_path = os.path.join(config.podcast.episodes_dir, "episode_script_clean.txt")
    with open(clean_script_path, "w") as f:
        f.write(clean_script)
    logger.info(f"Cleaned script saved to {clean_script_path}")

    out_file = os.path.join(config.podcast.episodes_dir, f"episode_{filename_suffix}.mp3")
    text_to_speech(clean_script, out_file)
    
    meta_file = os.path.join(config.podcast.episodes_dir, f"episode_metadata_{filename_suffix}.json")
    with open(meta_file, "w") as f:
        json.dump({
            "duration_minutes": config.processing.duration_minutes,
            "type": args.type,
            "title_prefix": args.title_prefix,
            "timestamp": timestamp
        }, f)
    logger.info(f"Saved metadata to {meta_file}")
    
    if not args.test:
        cleanup_old_episodes(config.podcast.episodes_dir, config.processing.retention_days)
        generate_episode_links_page(items, filename_suffix, config.podcast.episodes_dir)
        update_index_with_links(config.podcast.episodes_dir)
        generate_rss_feed(config)
    else:
        logger.info("Test mode: Skipping RSS feed generation.")

    logger.info("=== Done! ===")

if __name__ == "__main__":
    main()
