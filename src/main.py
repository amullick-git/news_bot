import argparse
import os
import json
from datetime import datetime
from urllib.parse import urlparse

from .config import load_config
from .utils import setup_logging, get_logger
from .fetcher import fetch_all, filter_last_24_hours, filter_by_keywords, get_friendly_source_names
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
    items = fetch_all(config.rss_sources, config.processing.max_per_feed)

    items = filter_last_24_hours(items)

    configure_gemini(api_key=os.getenv("GOOGLE_API_KEY"))

    if config.keywords:
        logger.info(f"Filtering by semantics (Gemini) for topics: {config.keywords}")
        items = filter_by_semantics(items, config.keywords, config.processing.gemini_model, limit=config.processing.max_final_articles)

    try:
        items.sort(key=lambda x: x["published"], reverse=True)
    except Exception:
        pass

    items = items[:config.processing.max_final_articles]

    if not items:
        logger.warning("No articles found. Try different keywords.")
        return

    logger.info(f"Using {len(items)} stories")
    
    os.makedirs(config.podcast.episodes_dir, exist_ok=True)

    target_words = config.processing.words_per_min * config.processing.duration_minutes
    logger.info(f"Target duration: {config.processing.duration_minutes} minutes (~{target_words} words)")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    sources_file = os.path.join(config.podcast.episodes_dir, f"episode_sources_{timestamp}.md")
    write_episode_sources(items, sources_file)

    friendly_sources = get_friendly_source_names(config.rss_sources)
    script = summarize_with_gemini(items, target_words, config.processing.gemini_model, friendly_sources)

    raw_script_path = os.path.join(config.podcast.episodes_dir, "episode_script_raw.txt")
    with open(raw_script_path, "w") as f:
        f.write(script)
    logger.info(f"Raw script saved to {raw_script_path}")

    clean_script = postprocess_for_tts_plain(script)

    clean_script_path = os.path.join(config.podcast.episodes_dir, "episode_script_clean.txt")
    with open(clean_script_path, "w") as f:
        f.write(clean_script)
    logger.info(f"Cleaned script saved to {clean_script_path}")

    out_file = os.path.join(config.podcast.episodes_dir, f"episode_{timestamp}.mp3")
    text_to_speech(clean_script, out_file)
    
    meta_file = os.path.join(config.podcast.episodes_dir, f"episode_metadata_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump({"duration_minutes": config.processing.duration_minutes}, f)
    logger.info(f"Saved metadata to {meta_file}")
    
    if not args.test:
        cleanup_old_episodes(config.podcast.episodes_dir, config.processing.retention_days)
        generate_episode_links_page(items, timestamp, config.podcast.episodes_dir)
        update_index_with_links(config.podcast.episodes_dir)
        generate_rss_feed(config)
    else:
        logger.info("Test mode: Skipping RSS feed generation.")

    logger.info("=== Done! ===")

if __name__ == "__main__":
    main()
