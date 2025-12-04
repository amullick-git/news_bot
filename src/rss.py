"""
RSS & HTML Generation
=====================

This module handles the generation of the podcast RSS feed and related HTML pages.
It includes functions for:
- Generating the `feed.xml` with iTunes tags.
- Creating HTML pages listing sources for each episode.
- Updating the main `index.html` with links to new episodes.
- Cleaning up old episodes based on retention policy.
"""
import os
import glob
import json
import re
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from feedgen.feed import FeedGenerator
from typing import List, Dict, Any
from .config import Config
from .utils import get_logger

logger = get_logger(__name__)

LINKS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Episode Sources - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f4f7f6;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #667eea;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 15px;
        }}
        .source-item {{
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }}
        .source-item:last-child {{
            border-bottom: none;
        }}
        .source-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
            display: block;
            color: #2d3748;
        }}
        .source-meta {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 20px;
            color: #555;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Episode Sources: {date_str}</h1>
        <div class="sources-list">
            {items_html}
        </div>
        <a href="../index.html" class="back-link">← Back to Home</a>
    </div>
</body>
</html>"""

def generate_episode_links_page(items: List[Dict[str, Any]], timestamp: str, episodes_dir: str) -> str:
    date_str = timestamp.replace("_", " ")
    
    items_html = ""
    for item in items:
        title = html.escape(item.get("title", "Untitled"))
        link = item.get("link", "#")
        source = urlparse(link).netloc
        
        items_html += f"""
        <div class="source-item">
            <a href="{link}" class="source-title" target="_blank">{title}</a>
            <div class="source-meta">Source: {source}</div>
        </div>
        """
        
    page_content = LINKS_PAGE_TEMPLATE.format(date_str=date_str, items_html=items_html)
    
    filename = f"links_{timestamp}.html"
    filepath = os.path.join(episodes_dir, filename)
    
    with open(filepath, "w") as f:
        f.write(page_content)
    
    logger.info(f"Generated links page: {filepath}")
    return filename

def update_index_with_links(episodes_dir: str):
    logger.info("Updating index.html with recent episodes...")
    
    link_files = glob.glob(os.path.join(episodes_dir, "links_*.html"))
    link_files.sort(reverse=True)
    
    links_html = ""
    for filepath in link_files:
        filename = os.path.basename(filepath)
        try:
            date_part = filename.replace("links_", "").replace(".html", "")
            dt = datetime.strptime(date_part, "%Y-%m-%d_%H")
            display_date = dt.strftime("%B %d, %Y - %I:%M %p")
        except ValueError:
            display_date = filename
            
        links_html += f"""
        <a href="{episodes_dir}/{filename}" class="episode-link-item">
            <span class="episode-link-date">{display_date}</span>
            <br>View News Sources
        </a>
        """
        
    try:
        with open("index.html", "r") as f:
            content = f.read()
            
        pattern = r'(<div class="links-list" id="episode-links-list">)(.*?)(</div>)'
        
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, f'\\1\n{links_html}\n\\3', content, flags=re.DOTALL)
            
            with open("index.html", "w") as f:
                f.write(new_content)
            logger.info("Updated index.html successfully.")
        else:
            logger.warning("Could not find #episode-links-list in index.html")
            
    except Exception as e:
        logger.error(f"Error updating index.html: {e}")

def cleanup_old_episodes(episodes_dir: str, retention_days: int):
    logger.info(f"Cleaning up old episodes (TTL: {retention_days} days)")
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    files = glob.glob(os.path.join(episodes_dir, "episode_*"))
    deleted_count = 0
    
    for file_path in files:
        filename = os.path.basename(file_path)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            date_str = match.group(1)
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    os.remove(file_path)
                    logger.info(f"Deleted old file: {filename}")
                    deleted_count += 1
            except ValueError:
                continue
                
    link_files = glob.glob(os.path.join(episodes_dir, "links_*.html"))
    for file_path in link_files:
        filename = os.path.basename(file_path)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            date_str = match.group(1)
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    os.remove(file_path)
                    logger.info(f"Deleted old links file: {filename}")
                    deleted_count += 1
            except ValueError:
                continue
                
    logger.info(f"Deleted {deleted_count} old files.")

def generate_rss_feed(config: Config):
    logger.info("Generating Podcast RSS Feed...")
    
    fg = FeedGenerator()
    fg.load_extension('podcast')
    
    fg.title(config.podcast.title)
    fg.description("A daily AI-generated news podcast.") # Could be in config too
    fg.link(href=config.podcast.base_url, rel='alternate')
    fg.link(href=f"{config.podcast.base_url}/feed.xml", rel='self')
    fg.language(config.podcast.language)
    fg.podcast.itunes_author(config.podcast.author)
    fg.podcast.itunes_owner(name=config.podcast.author, email="podcast@example.com")
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(config.podcast.image_url)
    fg.image(url=config.podcast.image_url, 
             title=config.podcast.title, 
             link=config.podcast.base_url)
    fg.podcast.itunes_category('News')
    
    episode_files = sorted(glob.glob(os.path.join(config.podcast.episodes_dir, "episode_*.mp3")), reverse=True)
    
    for mp3_path in episode_files:
        mp3_filename = os.path.basename(mp3_path)
        try:
            date_str = mp3_filename.replace("episode_", "").replace(".mp3", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d_%H")
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                display_title = dt.strftime("%Y-%m-%d %H:00 %Z")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                display_title = date_str
                
            dt_utc = dt.astimezone(timezone.utc)
            
            meta_filename = f"episode_metadata_{date_str}.json"
            meta_path = os.path.join(config.podcast.episodes_dir, meta_filename)
            
            title_prefix = "News Briefing"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        # Prefer explicitly stored prefix
                        if "title_prefix" in meta:
                            title_prefix = meta["title_prefix"]
                        else:
                            # Fallback inference for old episodes
                            duration = meta.get("duration_minutes", 15)
                            episode_type = meta.get("type", "daily")
                            
                            if episode_type == "weekly":
                                title_prefix = "Weekly News Round-up"
                            elif duration <= 5:
                                title_prefix = "Quick News Briefing"
                except Exception:
                    pass

        except ValueError:
            logger.warning(f"Skipping file with unexpected name format: {mp3_filename}")
            continue
            
        file_size = os.path.getsize(mp3_path)
        file_url = f"{config.podcast.base_url}/{config.podcast.episodes_dir}/{mp3_filename}"
        
        fe = fg.add_entry()
        fe.id(file_url)
        fe.title(f"{title_prefix}: {display_title}")
        fe.description(f"Daily news summary for {display_title}.")
        fe.link(href=file_url)
        fe.enclosure(file_url, str(file_size), 'audio/mpeg')
        fe.published(dt_utc)
        
    fg.rss_file('feed.xml')
    
    try:
        with open('feed.xml', 'r') as f:
            content = f.read()
        
        if '<?xml-stylesheet' not in content:
            xml_decl = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
            stylesheet = '\n<?xml-stylesheet type="text/xsl" href="rss_style.xsl"?>'
            if xml_decl in content:
                content = content.replace(xml_decl, xml_decl + stylesheet)
            else:
                content = stylesheet + content
                
            with open('feed.xml', 'w') as f:
                f.write(content)
            logger.info("Added stylesheet reference to feed.xml")
    except Exception as e:
        logger.error(f"Error adding stylesheet: {e}")

    logger.info("Generated feed.xml")
