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
    # timestamp arg is actually "type_datehash" suffix
    # Try to parse it for a nicer title
    try:
        # Expected: {type}_{yyyy-mm-dd_hh}
        # e.g. tech_daily_2024-12-06_17
        match = re.search(r"^(.*)_(\d{4}-\d{2}-\d{2}_\d{2})$", timestamp)
        if match:
            raw_type = match.group(1).replace("_", " ").title()
            date_part = match.group(2)
            dt = datetime.strptime(date_part, "%Y-%m-%d_%H")
            date_str = dt.strftime("%B %d, %Y - %I %p")
            page_title = f"{raw_type}: {date_str}"
        else:
            # Fallback
            page_title = timestamp.replace("_", " ")
    except:
        page_title = timestamp.replace("_", " ")

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
        
    page_content = LINKS_PAGE_TEMPLATE.format(date_str=page_title, items_html=items_html)
    
    filename = f"links_{timestamp}.html"
    filepath = os.path.join(episodes_dir, filename)
    
    with open(filepath, "w") as f:
        f.write(page_content)
    
    logger.info(f"Generated links page: {filepath}")
    return filename

def update_index_with_links(episodes_dir: str, index_path: str = "index.html"):
    logger.info(f"Updating {index_path} with recent episodes...")
    
    link_files = glob.glob(os.path.join(episodes_dir, "links_*.html"))
    
    # Filter out verification tests
    link_files = [f for f in link_files if "verification_test" not in os.path.basename(f)]
    
    # Sort files by date (parsed from filename) instead of string comparison
    files_with_dates = []
    for filepath in link_files:
        filename = os.path.basename(filepath)
        dt = datetime.min
        try:
            # Try to extract timestamp: YYYY-MM-DD_HH
            match = re.search(r"_(\d{4}-\d{2}-\d{2}_\d{2})\.html$", filename)
            if match:
                dt = datetime.strptime(match.group(1), "%Y-%m-%d_%H")
            else:
                # Fallback for simple date timestamps
                clean_name = filename.replace("links_", "").replace(".html", "")
                try:
                    dt = datetime.strptime(clean_name, "%Y-%m-%d_%H")
                except ValueError:
                    # Try YYYY-MM-DD
                     try:
                        dt = datetime.strptime(clean_name, "%Y-%m-%d")
                     except ValueError:
                        pass
        except Exception:
            pass
        files_with_dates.append({'dt': dt, 'path': filepath})
        
    # Sort descending by date
    files_with_dates.sort(key=lambda x: x['dt'], reverse=True)
    
    links_html = ""
    for item in files_with_dates:
        filepath = item['path']
        filename = os.path.basename(filepath)
        display_label = ""
        display_date = ""
        
        try:
            # Filename format: links_{type}_{timestamp}.html
            # Regex: match prefix "links_", then capture type group, then capture date group
            # e.g. links_tech_daily_2024-12-06_17.html
            match = re.search(r"links_(.*)_(\d{4}-\d{2}-\d{2}_\d{2})\.html$", filename)
            
            if match:
                raw_type = match.group(1).replace("_", " ").title() # e.g. Tech Daily
                date_part = match.group(2)
                dt = datetime.strptime(date_part, "%Y-%m-%d_%H")
                display_date = dt.strftime("%B %d, %Y - %I:%M %p")
                
                display_label = f"[{raw_type}]"
            else:
                 # Legacy fallback
                 date_part = filename.replace("links_", "").replace(".html", "")
                 # Try to parse date if possible, otherwise raw
                 try: 
                    dt = datetime.strptime(date_part, "%Y-%m-%d_%H")
                    display_date = dt.strftime("%B %d, %Y - %I:%M %p")
                 except:     
                    display_date = date_part
                 
        except Exception:
            display_date = filename
            
        full_text = f"{display_label} {display_date}".strip()
            
        if os.path.dirname(index_path):
             rel_dir = os.path.relpath(episodes_dir, os.path.dirname(index_path))
        else:
             rel_dir = episodes_dir
            
        # Derive MP3 filename
        mp3_filename = filename.replace("links_", "episode_").replace(".html", ".mp3")
        mp3_path = os.path.join(episodes_dir, mp3_filename)
        mp3_exists = os.path.exists(mp3_path)
        
        # Derive Metadata filename and extract voice info
        meta_filename = mp3_filename.replace("episode_", "episode_metadata_").replace(".mp3", ".json")
        meta_path = os.path.join(episodes_dir, meta_filename)
        
        # Fuzzy lookup if exact match fails
        if not os.path.exists(meta_path):
             # Try to match by timestamp suffix
             # mp3_filename: episode_{type}_{timestamp}.mp3
             # we want: episode_metadata_*{timestamp}.json
             match = re.search(r"_(\d{4}-\d{2}-\d{2}_\d{2})\.mp3$", mp3_filename)
             if match:
                 timestamp = match.group(1)
                 candidates = glob.glob(os.path.join(episodes_dir, f"episode_metadata_*{timestamp}.json"))
                 if candidates:
                     meta_path = candidates[0]

        voice_suffix = ""
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    voice = meta.get("voice_type", "")
                    if voice:
                        if "chirp" in voice:
                            if "hd" in voice.lower():
                                voice_suffix = " (Chirp HD)"
                            else:
                                voice_suffix = " (Chirp)"
                        elif "wavenet" in voice: voice_suffix = " (WaveNet)"
                        elif "neural" in voice: voice_suffix = " (Neural)"
                        elif "studio" in voice: voice_suffix = " (Studio)"
            except Exception:
                pass
        
        full_text = f"{display_label}{voice_suffix} {display_date}".strip()
        
        mp3_link = ""
        if mp3_exists:
             mp3_link = f'<a href="{rel_dir}/{mp3_filename}" style="color:#667eea;text-decoration:none;font-weight:500;">🎧 Play MP3</a>'
             
        links_html += f"""
        <div class="episode-entry" style="padding:15px; background:#f9f9f9; border-radius:8px; border-left:4px solid #667eea; margin-bottom:12px; transition: transform 0.2s ease;">
            <span class="episode-link-date" style="font-weight:bold; display:block; margin-bottom:8px; color:#333;">{full_text}</span>
            <div style="display:flex; gap:20px; font-size:0.95em;">
                <a href="{rel_dir}/{filename}" style="color:#667eea; text-decoration:none; font-weight:500;">📄 View Sources</a>
                {mp3_link}
            </div>
        </div>
        """
        
    try:
        content = ""
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                content = f.read()
        else:
            # Create basic structure if missing (e.g. in test mode)
            content = """<!DOCTYPE html>
<html>
<head><title>Podcast Gen</title></head>
<body>
    <h1>Latest Episodes</h1>
    <div class="links-list" id="episode-links-list">
        <!-- Links will be inserted here -->
    </div>
</body>
</html>"""
            
            
        pattern = r'(<!-- EPISODE_LIST_START -->)(.*?)(<!-- EPISODE_LIST_END -->)'
        
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, f'\\1\n{links_html}\n\\3', content, flags=re.DOTALL)
            
            with open(index_path, "w") as f:
                f.write(new_content)
            logger.info(f"Updated {index_path} successfully.")
        else:
            logger.warning(f"Could not find #episode-links-list in {index_path}")
            
    except Exception as e:
        logger.error(f"Error updating {index_path}: {e}")

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

def generate_rss_feed(config: Config, output_dir: str = "."):
    logger.info(f"Generating Podcast RSS Feed in {output_dir}...")
    
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
    
    # Filter out verification tests
    episode_files = [f for f in episode_files if "verification_test" not in os.path.basename(f)]
    
    for mp3_path in episode_files:
        mp3_filename = os.path.basename(mp3_path)
        try:
            # New format: episode_{type}_{timestamp}.mp3
            # Or legacy format: episode_{timestamp}.mp3
            # Using regex to extract timestamp at the end
            match = re.search(r"_(\d{4}-\d{2}-\d{2}_\d{2})\.mp3$", mp3_filename)
            if not match:
                 # Try date-only match for older files
                 match = re.search(r"_(\d{4}-\d{2}-\d{2})\.mp3$", mp3_filename)
            
            if match:
                date_str = match.group(1)
                # Determine type from filename part before timestamp
                # format: episode_{type}_{timestamp}.mp3
                # prefix: episode_
                # suffix: _{timestamp}.mp3
                type_part = mp3_filename[len("episode_"):match.start()]
                
                # If type_part ends with underscore, strip it (should always be empty/valid)
                # For legacy 'episode_2024...' type_part might be empty
                if not type_part:
                    type_part = "legacy"
            else:
                # Fallback purely for legacy if regex fails (shouldn't happen with strict naming)
                date_str = mp3_filename.replace("episode_", "").replace(".mp3", "")
                type_part = "legacy"

            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d_%H")
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                # User-friendly date format with hour: December 06, 2024 - 02 PM
                display_title = dt.strftime("%B %d, %Y - %I %p")
            except ValueError:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                display_title = dt.strftime("%B %d, %Y")
                
            dt_utc = dt.astimezone(timezone.utc)
            
            # Construct metadata filename based on MP3 filename pattern
            # It matches the suffix of the MP3: episode_metadata_{type}_{timestamp}.json
            meta_filename = mp3_filename.replace("episode_", "episode_metadata_").replace(".mp3", ".json")
            meta_path = os.path.join(config.podcast.episodes_dir, meta_filename)
            
            title_prefix = "News Briefing"
            title_suffix = ""
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        
                        # Get Title Prefix
                        if "title_prefix" in meta:
                            title_prefix = meta["title_prefix"]
                        else:
                            # Determine title from type (format: {content}_{frequency})
                            # Parse content and frequency
                            parts = episode_type.split('_')
                            content_type = parts[0] if parts else "general"
                            frequency = parts[1] if len(parts) > 1 else "daily"
                            
                            # Set title prefix based on content type and frequency
                            if content_type == "tech":
                                title_prefix = "Tech News Briefing" if frequency == "daily" else "Tech Weekly Round-up"
                            elif content_type == "kids":
                                title_prefix = "Kids News"
                            elif content_type == "general":
                                if frequency == "weekly":
                                    title_prefix = "Weekly News Round-up"
                                elif frequency == "evening":
                                    title_prefix = "Quick News Briefing"
                                else:  # daily
                                    title_prefix = "News Briefing"
                            
                        # Get Voice Label
                        voice = meta.get("voice_type")
                        if voice:
                            if "chirp" in voice: title_suffix = " (Chirp)"
                            elif "wavenet" in voice: title_suffix = " (WaveNet)"
                            elif "neural" in voice: title_suffix = " (Neural)"
                            elif "studio" in voice: title_suffix = " (Studio)"
                            
                except Exception:
                    pass
                    
            # Logic to infer title from filename if metadata missing
            # Parse type from filename (e.g., episode_general_daily_2025-12-07.mp3)
            parts = type_part.split('_')
            content_type = parts[0] if parts else "general"
            frequency = parts[1] if len(parts) > 1 else "daily"
            
            if content_type == "tech":
                title_prefix = "Tech News Briefing" if frequency == "daily" else "Tech Weekly Round-up"
            elif content_type == "kids":
                title_prefix = "Kids News"
            elif content_type == "general":
                if frequency == "weekly":
                    title_prefix = "Weekly News Round-up"
                elif frequency == "evening":
                    title_prefix = "Quick News Briefing"
                else:  # daily
                    title_prefix = "News Briefing"
 
        except ValueError:
            logger.warning(f"Skipping file with unexpected name format: {mp3_filename}")
            continue
            
        file_size = os.path.getsize(mp3_path)
        # GitHub Pages serves /docs as root, strip 'docs/' from URL
        web_path = config.podcast.episodes_dir.replace("docs/", "")
        file_url = f"{config.podcast.base_url}/{web_path}/{mp3_filename}"
        
        fe = fg.add_entry()
        fe.id(file_url)
        fe.title(f"{title_prefix}{title_suffix} - {display_title}")
        fe.description(f"Daily news summary for {display_title}.")
        fe.link(href=file_url)
        fe.enclosure(file_url, str(file_size), 'audio/mpeg')
        fe.published(dt_utc)
        
    feed_path = os.path.join(output_dir, 'feed.xml')
    fg.rss_file(feed_path)
    
    try:
        with open(feed_path, 'r') as f:
            content = f.read()
        
        if '<?xml-stylesheet' not in content:
            xml_decl = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
            stylesheet = '\n<?xml-stylesheet type="text/xsl" href="rss_style.xsl"?>'
            if xml_decl in content:
                content = content.replace(xml_decl, xml_decl + stylesheet)
            else:
                content = stylesheet + content
                
            with open(feed_path, 'w') as f:
                f.write(content)
            logger.info("Added stylesheet reference to feed.xml")
    except Exception as e:
        logger.error(f"Error adding stylesheet: {e}")

    logger.info(f"Generated {feed_path}")
