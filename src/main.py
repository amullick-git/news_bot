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
    parser.add_argument("--no-tts", action="store_true", help="Skip Text-to-Speech generation (script only)")
    parser.add_argument("--voice-type", type=str, default=None, choices=["wavenet", "neural", "studio", "chirp3-hd"], help="TTS Voice type: wavenet (default), neural, studio, or chirp3-hd")
    args = parser.parse_args()

    setup_logging()
    config = load_config()
    
    # Configure Gemini
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        configure_gemini(api_key)
    else:
        logger.warning("GOOGLE_API_KEY not set. Gemini calls may fail if not using ADC.")

    # Override config with args if provided
    if args.duration:
        config.processing.duration_minutes = args.duration
    
    # --- OUTPUT DIRECTORY SETUP ---
    # Sandbox directory (root for all outputs in this run)
    sandbox_dir = "."
    if args.test:
        logger.info("TEST MODE ENABLED")
        sandbox_dir = "test_output"
        
    # Create structure
    # web_dir: contains public facing content (index.html, feed.xml, episodes/, assets/)
    web_dir = os.path.join(sandbox_dir, "docs")
    os.makedirs(web_dir, exist_ok=True)
    
    # metrics_dir: contains internal logs (handled by MetricsLogger using sandbox_dir)
    # Note: MetricsLogger(sandbox_dir) will append /metrics automatically.
    
    logger.info(f"Sandbox: {sandbox_dir}")
    logger.info(f"Web Root: {web_dir}")

    # Episodes directory is nested under web_dir
    config.podcast.episodes_dir = os.path.join(web_dir, "episodes")
    os.makedirs(config.podcast.episodes_dir, exist_ok=True)
    logger.info(f"Episodes directory: {config.podcast.episodes_dir}")

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
    # Apply processing overrides
    # Priority 1: Exact type match (e.g. 'evening', 'tech_weekly')
    if config.processing_overrides and args.type in config.processing_overrides:
        logger.info(f"Applying processing overrides for type: {args.type}")
        config.processing = config.processing_overrides[args.type]
    # Priority 2: Feed category match (e.g. 'tech', 'kids') - ONLY if not already overridden by type
    elif config.processing_overrides and feed_key in config.processing_overrides:
        logger.info(f"Applying processing overrides for category: {feed_key}")
        config.processing = config.processing_overrides[feed_key]
        
    # Re-apply CLI duration override if provided, as it should take precedence
    if args.duration:
        config.processing.duration_minutes = args.duration

    # Selected feeds
    selected_feeds = config.feeds.get(feed_key, config.feeds["general"])
    logger.info(f"Selected feed category: {feed_key} ({len(selected_feeds)} feeds)")
    
    # FETCH STEP: Use deep fetch limit (e.g. 100) to ensure history coverage
    fetch_limit = getattr(config.processing, "fetch_limit", 100)
    
    # --- METRICS CHECKPOINT 1 ---
    fetched_items = fetch_all(selected_feeds, fetch_limit)
    
    lookback_hours = args.lookback_days * 24
    items = filter_by_time_window(fetched_items, hours=lookback_hours)

    configure_gemini(api_key=os.getenv("GOOGLE_API_KEY"))

    # Select keywords based on type
    kw_key = feed_key # "tech", "kids", or "general"
    selected_keywords = config.keywords.get(kw_key, config.keywords["general"])

    # TWO-STAGE HYBRID FILTERING:
    stage1_count = None
    if selected_keywords:
        # STAGE 1: Local AI Pre-Filter (Semantic Relevance Only)
        from .local_ai import LocalFilter
        local_bot = LocalFilter()
        
        prefilter_limit = getattr(config.processing, "local_prefilter_limit", 50)
        candidates = local_bot.filter_by_relevance(
            items, 
            topics=selected_keywords, 
            model_name=getattr(config.processing, "local_model", "all-MiniLM-L6-v2"),
            limit=prefilter_limit,  # Stage 1: Reduce to ~50 candidates
            threshold=0.15
        )
        
        
        stage1_count = len(candidates)
        logger.info(f"Stage 1 (Local AI): {len(items)} → {len(candidates)} candidates")
        
        # STAGE 2: Gemini Final Selection (Breaking News, Diversity, Ordering)
        from .content import filter_by_semantics
        items = filter_by_semantics(
            candidates,
            topics=selected_keywords,
            model_name=config.processing.gemini_model,
            limit=config.processing.max_final_articles  # Stage 2: Final selection
        )
        
        logger.info(f"Stage 2 (Gemini): {len(candidates)} → {len(items)} final articles")
    else:
        # Fallback if no keywords
        from .fetcher import limit_by_source
        items = limit_by_source(items, 5)
        items = items[:config.processing.max_final_articles]

    # --- METRICS CHECKPOINT 2 ---
    shortlisted_items = items

    if not items:
        logger.warning("No articles found after filtering.")
        return

    logger.info(f"Using {len(items)} stories")
    
    os.makedirs(config.podcast.episodes_dir, exist_ok=True)

    target_words = config.processing.words_per_min * config.processing.duration_minutes
    logger.info(f"Target duration: {config.processing.duration_minutes} minutes (~{target_words} words)")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    filename_suffix = f"{args.type}_{timestamp}"

    sources_file = os.path.join(config.podcast.episodes_dir, f"episode_sources_{filename_suffix}.md")
    write_episode_sources(items, sources_file)

    import random
    friendly_sources = get_friendly_source_names(items, limit=random.randint(3, 4), randomize=True)
    
    # Determine audience
    audience = "kids" if "kids" in args.type else "general"
    
    script = summarize_with_gemini(
        items, 
        target_words=target_words, 
        model_name=config.processing.gemini_model, 
        friendly_sources=friendly_sources, 
        audience=audience,
        show_name=args.title_prefix,
        keywords=selected_keywords
    )

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
    
    episode_path = os.path.join(config.podcast.episodes_dir, f"episode_{filename_suffix}.mp3")
    
    meta_file = os.path.join(config.podcast.episodes_dir, f"episode_metadata_{filename_suffix}.json")
    with open(meta_file, "w") as f:
        json.dump({
            "duration_minutes": config.processing.duration_minutes,
            "type": args.type,
            "title_prefix": args.title_prefix,
            "timestamp": timestamp,
            "voice_type": config.processing.voice_type
        }, f)
    logger.info(f"Saved metadata to {meta_file}")

    # 6. Generate Audio (TTS)
    tts_chars = 0
    if not args.no_tts:
        tts_chars = text_to_speech(clean_script, episode_path, voice_type=config.processing.voice_type)
        logger.info("Audio generation complete.")
    else:
        logger.info("Skipping TTS generation (--no-tts provided).")
    
    links_filename = None
    links_filename = None
     
    cleanup_old_episodes(config.podcast.episodes_dir, config.processing.retention_days)
    
    # Capture the generated filename (e.g. links_daily_2024...html)
    links_filename = generate_episode_links_page(items, filename_suffix, config.podcast.episodes_dir)
    
    # Update index.html in the web directory (docs/)
    index_path = os.path.join(web_dir, "index.html")
    update_index_with_links(config.podcast.episodes_dir, index_path=index_path)
    
    generate_rss_feed(config, output_dir=web_dir)
        
    # --- LOG METRICS ---
    from .metrics import MetricsLogger
    metrics = MetricsLogger(sandbox_dir)
    
    tts_stats = {
        "model": config.processing.voice_type,
        "chars": tts_chars
    }
    
    metrics.log_run(fetched_items, shortlisted_items, args.type, args.test, links_file=links_filename, local_ai_items=candidates if selected_keywords else None, tts_stats=tts_stats)

    logger.info("=== Done! ===")

if __name__ == "__main__":
    main()
