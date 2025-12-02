import html
import re
import os
import time
import textwrap
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from urllib.parse import urlparse
import email.utils as email_date_parser
import requests
import json
import html
import re
import feedparser


import google.generativeai as genai
from google.cloud import texttospeech
from feedgen.feed import FeedGenerator
import glob


###########################################
# CONFIG
###########################################

# RSS sources you want
RSS_SOURCES = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.feedburner.com/ndtvnews-india-news",
    "https://hnrss.org/frontpage",
    "https://www.theverge.com/rss/index.xml", # Tech
    "https://www.cnbc.com/id/100003114/device/rss/rss.html", # Business
    "https://feeds.npr.org/1001/rss.xml" # General
]

# keywords to filter (optional)
KEYWORDS = ["USA", "world", "ai", "technology", "market", "election", "india", "economy", "business", "sports", "health"]

# duration target
DURATION_MINUTES = 15
WORDS_PER_MIN = 150
TARGET_WORDS = WORDS_PER_MIN * DURATION_MINUTES

# Article limits
MAX_PER_FEED = 10      # How many items to fetch per RSS feed
MAX_FINAL_ARTICLES = 20 # How many articles to include in the final script

# Podcast Hosting Config
# REPLACE THIS with your actual GitHub Pages URL or hosting URL
BASE_URL = "https://amullick-git.github.io/news_bot"

PODCAST_METADATA = {
    "title": "Amarnath's Daily News Briefing",
    "description": "A daily AI-generated news podcast covering world events, technology, and more.",
    "author": "Amarnath Mullick",
    "image": f"{BASE_URL}/cover_v2.png",
    "language": "en"
}

EPISODES_DIR = "episodes"
RETENTION_DAYS = 7 # Keep episodes for 7 days


###########################################
# NEWS FETCHING
###########################################

def fetch_feed(url, max_items=10):
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


def fetch_all():
    all_items = []
    for url in RSS_SOURCES:
        try:
            all_items.extend(fetch_feed(url, max_items=MAX_PER_FEED))
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    return all_items

def write_episode_sources(items, filename):
    """
    Write the list of chosen news items (title + source + URL)
    to a text/markdown file.
    """
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
    print(f"Episode sources saved to {filename}")


###########################################
# FILTERING
###########################################

from datetime import datetime, timedelta
import email.utils as email_date_parser   # parses RFC822 dates

def parse_published_date(published_str):
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


def filter_last_24_hours(items):
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

    return filtered

def filter_by_keywords(items, keywords):
    out = []
    key_low = [k.lower() for k in keywords]
    for it in items:
        block = (it["title"] + " " + it["summary"]).lower()
        if any(k in block for k in key_low):
            out.append(it)
    return out

def filter_by_semantics(items, topics, limit=10):
    """
    Use Gemini to filter news items based on semantic relevance to topics.
    """
    if not items or not topics:
        return items

    print(f"  - Sending {len(items)} items to Gemini for semantic filtering...")

    # Prepare the list of items for the prompt
    items_text = ""
    for i, item in enumerate(items):
        # limit summary length to save tokens/noise
        summary = (item.get('summary') or "")[:300]
        items_text += f"Item {i}:\nTitle: {item.get('title')}\nSummary: {summary}\n\n"

    prompt = f"""
    You are a news editor. Your task is to select the top {limit} stories that are relevant to the following topics: {', '.join(topics)}.

    **CRITICAL SELECTION CRITERIA:**
    1. **Relevance:** Must match at least one of the topics.
    2. **Ordering:** Return the stories ordered strictly by the topics provided above. For example, if topics are "A, B", list all A stories first, then all B stories.
    3. **Importance:** Within each topic, prioritize critical/breaking news.
    4. **Diversity:** Ensure a good mix of different topics.
    5. **News vs Opinion:** STRICTLY EXCLUDE opinion pieces, editorials, commentaries, reviews, and "analysis" that is not grounded in new facts. Prioritize hard news.
    6. **Substance:** Exclude fluff, clickbait, or purely promotional content.

    Here are the candidate stories:
    {items_text}

    Return a JSON list of the indices (0-based) of the selected stories.
    Target count: ~{limit} stories (return fewer if not enough good matches).
    Example output: [0, 2, 5]
    Return ONLY the JSON list.
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        
        text = response.text.strip()
        # clean up potential markdown formatting
        if text.startswith("```"):
            # remove first line
            text = text.split("\n", 1)[1]
            # remove last line if it is backticks
            if text.strip().endswith("```"):
                text = text.rsplit("\n", 1)[0]
        
        import json
        relevant_indices = json.loads(text)
        
        filtered_items = [items[i] for i in relevant_indices if isinstance(i, int) and 0 <= i < len(items)]
        return filtered_items

    except Exception as e:
        print(f"Error in semantic filtering: {e}")
        return []



###########################################
# GEMINI SUMMARIZATION → FULL PODCAST SCRIPT
###########################################

def get_friendly_source_names():
    """
    Derive friendly names from RSS_SOURCES for the intro.
    """
    names = set()
    for url in RSS_SOURCES:
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

def summarize_with_gemini(articles, target_words):
    # genai.configure is now called in main()


    model = genai.GenerativeModel("gemini-2.5-flash")

    articles_block = ""
    for idx, a in enumerate(articles, 1):
        articles_block += f"""
### Story {idx}
Title: {a['title']}
Summary: {a['summary']}
Source: {a['link']}
"""

    prompt = f"""
    You are writing a script for a professional news podcast featuring two speakers: a HOST and a REPORTER.

    **Format:**
    - Use "HOST:" for lines spoken by the host (Rob).
    - Use "REPORTER:" for lines spoken by the reporter (Sarah).
    - Write in a conversational, engaging, yet professional tone.
    - Don't keep repeating the name of the reporter or host in the conversation.
    - The HOST introduces the show, transitions between topics, and asks the REPORTER for details.
    - The REPORTER provides the in-depth news summaries and analysis.
    - End with the HOST signing off.

    **Constraints:**
    - Total length: ~{target_words} words.
    - Do NOT use markdown formatting (bold, italics) in the spoken text.
    - Do NOT include sound effects or music cues.
    - Ensure smooth transitions between stories.
    - Do NOT add any opinionated or editorialized language.

    **Source Material:**
    {articles_block}

    **Structure:**
    1. HOST: Intro (Welcome to Rob's Daily News Briefing...). IMPORTANT: In the intro, explicitly mention that we are covering news from {get_friendly_source_names()} and others.
    2. HOST & REPORTER: Dialogue covering the top stories. Group related stories together.
    3. HOST: Outro.
    """

    response = model.generate_content(prompt)
    return response.text


###########################################
# GOOGLE TTS
###########################################


STAGE_DIRECTION_PATTERNS = [
    r'\([^)]*\)',          # (Intro music), (SFX: boom), etc.
    r'\[[^\]]*\]',         # [Soft music], [Applause], etc.
    r'\*[^*]*\*',          # *applause*, *laughs*, *emphasis*
]

def remove_stage_directions(text: str) -> str:
    # Remove inline ( ... ), [ ... ], * ... *
    for pat in STAGE_DIRECTION_PATTERNS:
        text = re.sub(pat, '', text)

    # Remove whole lines that look like cues: SFX:, MUSIC:, FX:
    text = re.sub(
        r'^(?:sfx|fx|music|sound|audio)\s*[:\-].*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Remove lines that are just things like "Intro music fades", etc.
    text = re.sub(
        r'^\s*(intro|outro|background)\s+music.*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    return text


def strip_markdown_formatting(text: str) -> str:
    # Remove markdown headings (keep content)
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)

    # Remove bullet symbols at start of line: -, *, •
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)

    # Remove numbered list prefixes like "1. " or "2) "
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)

    # Remove leftover double asterisks / underscores
    text = text.replace('**', '').replace('__', '')

    return text


def collapse_whitespace(text: str) -> str:
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Keep paragraph breaks but avoid huge gaps
    # First, collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Inside paragraphs, collapse multiple spaces/tabs
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split('\n')]
    # Rebuild, preserving blank lines as paragraph separators
    cleaned_lines = []
    for line in lines:
        if line:
            cleaned_lines.append(line)
        else:
            cleaned_lines.append('')  # keep empty line

    # Join back with newlines and then clean leading/trailing space
    return '\n'.join(cleaned_lines).strip()


def ensure_sentence_punctuation(text: str) -> str:
    """
    Ensure most lines end with ., ?, or ! for smoother TTS.
    We don’t touch lines that clearly look like section titles (single short words).
    """
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append('')
            continue

        # If it already ends in sentence punctuation, keep as is
        if stripped[-1] in '.?!':
            new_lines.append(stripped)
            continue

        # Very short lines (like “Today” / “Intro”) – leave them
        if len(stripped.split()) <= 2:
            new_lines.append(stripped)
            continue

        # Otherwise, append a period
        new_lines.append(stripped + '.')
    return '\n'.join(new_lines)


def flatten_for_tts(text: str) -> str:
    """
    Final flattening step: turn paragraphs into a nicely flowing TTS string.
    Keeps paragraph breaks as slight pauses (newlines).
    """
    text = dedent(text).strip()

    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Some TTS engines treat \n as slight breaks,
    # so we keep double newlines as paragraph pauses.
    return text.strip()


def postprocess_for_tts_plain(raw_script: str) -> str:
    """
    Advanced postprocessor pipeline for plain text TTS.
    1. Remove stage directions / SFX cues
    2. Strip markdown / bullets
    3. Normalize whitespace
    4. Ensure sentences have punctuation
    5. Flatten into clean paragraphs
    """
    text = raw_script

    text = remove_stage_directions(text)
    text = strip_markdown_formatting(text)
    text = collapse_whitespace(text)
    text = ensure_sentence_punctuation(text)
    text = flatten_for_tts(text)

    return text



def classify_paragraph(p: str) -> str:
    """Classify the paragraph type for pacing heuristics."""
    pl = p.strip().lower()

    # Very simple heuristics – tweak as you like
    if pl.startswith(("welcome", "good morning", "good evening", "this is", "you’re listening", "you're listening")):
        return "intro"
    if pl.startswith(("that’s it", "that's it", "that is it",
                      "thanks for listening", "thank you for listening",
                      "see you next time", "we’ll be back", "we'll be back",
                      "until next time")):
        return "outro"

    length = len(p)
    if length < 120:
        return "short"
    if length > 450:
        return "long"

    return "normal"


def pacing_for_type(kind: str):
    """
    Map a paragraph type to (prosody_rate, break_time_ms).
    prosody_rate is SSML rate: 'slow', 'medium', 'fast', 'x-fast', or percentage like '110%'.
    """
    if kind == "intro":
        return "fast", 900   # steady, slightly longer pause
    if kind == "outro":
        return "medium", # calmer ending
    if kind == "short":
        return "fast", 500     # quick little lines
    if kind == "long":
        return "fast", 800   
    # normal
    return "medium", 600


def make_ssml_paragraph(text: str) -> str:
    """
    Convert a single paragraph text into its SSML representation
    with appropriate prosody and break.
    """
    kind = classify_paragraph(text)
    rate, break_ms = pacing_for_type(kind)
    escaped = html.escape(text)
    
    # Reduce pause duration for commas (default is too long)
    # Replace ", " with a weak break to tighten the flow
    escaped = escaped.replace(", ", '<break strength="weak"/> ')
    
    # We add the break at the end of every paragraph to ensure pacing 
    # is preserved even across chunk boundaries.
    return f'<p><prosody rate="{rate}">{escaped}</prosody></p><break time="{break_ms}ms"/>'

def generate_ssml_chunks(text: str, max_bytes=5000) -> list[str]:
    """
    Convert text to SSML chunks that strictly respect the byte limit.
    1. Split into paragraphs.
    2. Convert each paragraph to SSML.
    3. Accumulate into chunks.
    """
    # 1. Split into paragraphs and handle huge ones
    raw_paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    
    # Flatten huge paragraphs if needed
    flat_paragraphs = []
    for p in raw_paragraphs:
        # If a single paragraph is crazy long (unlikely in news, but possible),
        # split it by sentences to be safe.
        if len(p) > 2000: 
             sentences = re.split(r'(?<=[.!?]) +', p)
             flat_paragraphs.extend([s for s in sentences if s])
        else:
            flat_paragraphs.append(p)
            
    chunks = []
    
    # Overhead for <speak>...</speak>
    wrapper_overhead = len("<speak>\n\n</speak>")
    
    current_chunk_ssml = ""
    current_size = wrapper_overhead
    
    for p in flat_paragraphs:
        ssml_part = make_ssml_paragraph(p)
        part_len = len(ssml_part.encode("utf-8"))
        
        # If this single part is too big, we have a problem. 
        # (Should be handled by the splitting above, but safety check)
        if part_len + wrapper_overhead > max_bytes:
            print(f"Warning: Dropping a paragraph that exceeds {max_bytes} bytes even alone.")
            continue
            
        if current_size + part_len > max_bytes:
            # Finish current chunk
            chunks.append(f"<speak>\n{current_chunk_ssml}\n</speak>")
            # Start new chunk
            current_chunk_ssml = ssml_part
            current_size = wrapper_overhead + part_len
        else:
            # Add to current
            if current_chunk_ssml:
                current_chunk_ssml += "\n"
            current_chunk_ssml += ssml_part
            current_size += part_len + 1 # +1 for newline
            
    # Add last chunk
    if current_chunk_ssml:
        chunks.append(f"<speak>\n{current_chunk_ssml}\n</speak>")
        
    return chunks

from google.cloud import texttospeech

def text_to_speech(clean_script, output_file="episode.mp3"):
    print("\n=== Converting to speech using Google TTS (Smart SSML Chunking)... ===")

    client = texttospeech.TextToSpeechClient()

    # Generate safe SSML chunks directly
    # We need to handle speaker switching now
    
    # 1. Parse the script into segments (speaker, text)
    segments = []
    current_speaker = "HOST" # Default
    current_text = []
    
    lines = clean_script.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("HOST:"):
            # If we were collecting text for REPORTER, save it
            if current_speaker == "REPORTER" and current_text:
                segments.append(("REPORTER", "\n".join(current_text)))
                current_text = []
            current_speaker = "HOST"
            content = line.replace("HOST:", "").strip()
            if content:
                current_text.append(content)
                
        elif line.startswith("REPORTER:"):
            # If we were collecting text for HOST, save it
            if current_speaker == "HOST" and current_text:
                segments.append(("HOST", "\n".join(current_text)))
                current_text = []
            current_speaker = "REPORTER"
            content = line.replace("REPORTER:", "").strip()
            if content:
                current_text.append(content)
        else:
            # Continuation of current speaker
            current_text.append(line)
            
    # Add final segment
    if current_text:
        segments.append((current_speaker, "\n".join(current_text)))

    print(f"Parsed {len(segments)} dialogue segments.")

    audio_contents = []

    # Voice configurations
    voice_host = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D", # Male voice for Host
    )
    voice_reporter = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-F", # Female voice for Reporter
    )

    # Let SSML handle local pacing; keep global rate at 1.2
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.2,
        pitch=0.0,
        volume_gain_db=0.0,
    )

    for idx, (speaker, text) in enumerate(segments, 1):
        print(f"  Synthesizing segment {idx}/{len(segments)} ({speaker})...")
        
        # Use existing SSML chunking logic for each segment
        # This handles long monologues by a single speaker
        ssml_chunks = generate_ssml_chunks(text, max_bytes=4800)
        
        voice = voice_host if speaker == "HOST" else voice_reporter
        
        for ssml in ssml_chunks:
            synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
            try:
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config,
                )
                audio_contents.append(response.audio_content)
            except Exception as e:
                print(f"Error synthesizing chunk: {e}")

    # Concatenate all MP3 chunks
    with open(output_file, "wb") as out:
        for content in audio_contents:
            out.write(content)

    print(f"Saved audio file: {output_file}")



###########################################
# RSS FEED GENERATION
###########################################

def generate_rss_feed():
    print("\n=== Generating Podcast RSS Feed... ===")
    
    fg = FeedGenerator()
    fg.load_extension('podcast')
    
    fg.title(PODCAST_METADATA["title"])
    fg.description(PODCAST_METADATA["description"])
    fg.link(href=BASE_URL, rel='alternate')
    fg.language(PODCAST_METADATA["language"])
    fg.podcast.itunes_author(PODCAST_METADATA["author"])
    fg.podcast.itunes_image(PODCAST_METADATA["image"])
    fg.image(PODCAST_METADATA["image"]) # Standard RSS image tag
    fg.podcast.itunes_category('News')
    
    # Find all generated MP3 episodes
    # Assuming format: episodes/episode_YYYY-MM-DD_HH.mp3
    episode_files = sorted(glob.glob(os.path.join(EPISODES_DIR, "episode_*.mp3")), reverse=True)
    
    for mp3_path in episode_files:
        mp3_filename = os.path.basename(mp3_path)
        # Parse date from filename
        try:
            # filename example: episode_2025-11-30_15.mp3 or episode_2025-11-30.mp3
            date_str = mp3_filename.replace("episode_", "").replace(".mp3", "")
            
            # Try parsing with hour first
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d_%H")
                # Assume filename time is in local system time
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                display_title = dt.strftime("%Y-%m-%d %H:00 %Z")
            except ValueError:
                # Fallback to day only
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                display_title = date_str
                
            # Convert to UTC for the feed (RSS standard)
            dt_utc = dt.astimezone(timezone.utc)
            
            # Check for metadata file to determine type
            # Filename: episode_metadata_YYYY-MM-DD_HH.json
            meta_filename = f"episode_metadata_{date_str}.json"
            meta_path = os.path.join(EPISODES_DIR, meta_filename)
            
            title_prefix = "News Briefing"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        duration = meta.get("duration_minutes", 15)
                        if duration <= 5:
                            title_prefix = "Quick News Briefing"
                except Exception:
                    pass
            # Fallback heuristic for legacy files (optional, or just default to News Briefing)
            elif dt.hour == 19: # 7 PM
                 title_prefix = "Quick News Briefing"
                
        except ValueError:
            print(f"Skipping file with unexpected name format: {mp3_filename}")
            continue
            
        file_size = os.path.getsize(mp3_path)
        # URL needs to point to the episodes directory
        file_url = f"{BASE_URL}/{EPISODES_DIR}/{mp3_filename}"
        
        fe = fg.add_entry()
        fe.id(file_url)
        fe.title(f"{title_prefix}: {display_title}")
        fe.description(f"Daily news summary for {display_title}.")
        fe.enclosure(file_url, str(file_size), 'audio/mpeg')
        fe.published(dt_utc)
        
    fg.rss_file('feed.xml')
    
    # Inject stylesheet reference
    try:
        with open('feed.xml', 'r') as f:
            content = f.read()
        
        if '<?xml-stylesheet' not in content:
            # Insert after XML declaration
            xml_decl = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
            stylesheet = '\n<?xml-stylesheet type="text/xsl" href="rss_style.xsl"?>'
            if xml_decl in content:
                content = content.replace(xml_decl, xml_decl + stylesheet)
            else:
                # Fallback if no declaration found (unlikely)
                content = stylesheet + content
                
            with open('feed.xml', 'w') as f:
                f.write(content)
            print("Added stylesheet reference to feed.xml")
    except Exception as e:
        print(f"Error adding stylesheet: {e}")

    print("Generated feed.xml")


def cleanup_old_episodes():
    """
    Delete episodes and related files older than RETENTION_DAYS.
    """
    print(f"\n=== Cleaning up old episodes (TTL: {RETENTION_DAYS} days) ===")
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    # Find all episode files
    files = glob.glob(os.path.join(EPISODES_DIR, "episode_*"))
    # This glob matches episode_metadata_*.json too, so the loop below just needs to handle the date parsing correctly.
    # The regex r"(\d{4}-\d{2}-\d{2})" will match the date in "episode_metadata_2025-12-01_07.json" just fine.
    # So actually, no code change is needed in the loop logic itself, 
    # but I should verify the regex works for the new filename format.
    # "episode_metadata_2025-12-01_07.json" -> match group 1 is "2025-12-01". Correct.
    
    # However, I will add a comment to be explicit.
    
    deleted_count = 0
    for file_path in files:
        filename = os.path.basename(file_path)
        
        # Extract date from filename: episode_YYYY-MM-DD...
        # Matches episode_2025-12-01.mp3, episode_sources_2025-12-01.md, etc.
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            date_str = match.group(1)
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    os.remove(file_path)
                    print(f"Deleted old file: {filename}")
                    deleted_count += 1
            except ValueError:
                continue
                
    if deleted_count == 0:
        print("No old files to delete.")
    else:
        print(f"Deleted {deleted_count} old files.")




###########################################
# MAIN PIPELINE
###########################################

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=15, help="Target duration in minutes")
    parser.add_argument("--test", action="store_true", help="Run in test mode (save to test_episodes/, no RSS update)")
    args = parser.parse_args()

    if args.test:
        print("TEST MODE ENABLED")
        global EPISODES_DIR
        EPISODES_DIR = "test_episodes"
        print(f"Output directory set to: {EPISODES_DIR}")

    print("\n=== Fetching news… ===")
    items = fetch_all()

    # Filter items from last 24 hours
    items = filter_last_24_hours(items)
    print(f"Items from last 24 hours: {len(items)}")

    # Configure Gemini once
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    if KEYWORDS:
        print("Filtering by semantics (Gemini) for topics:", KEYWORDS)

        items = filter_by_semantics(items, KEYWORDS, limit=MAX_FINAL_ARTICLES)

    # sort by published time, if available
    try:
        items.sort(key=lambda x: x["published"], reverse=True)
    except Exception:
        pass

    # choose top stories
    items = items[:MAX_FINAL_ARTICLES]

    if not items:
        print("No articles found. Try different keywords.")
        return

    print(f"Using {len(items)} stories")
    
    # Ensure episodes directory exists
    os.makedirs(EPISODES_DIR, exist_ok=True)

    duration_minutes = args.duration
    print(f"Target duration: {duration_minutes} minutes")
    
    target_words = WORDS_PER_MIN * duration_minutes

    # write a file listing the chosen stories for this episode
    # Include hour in timestamp to allow multiple runs per day
    # Use local system time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    sources_file = os.path.join(EPISODES_DIR, f"episode_sources_{timestamp}.md")
    write_episode_sources(items, sources_file)

    # 1) produce the raw script from Gemini
    script = summarize_with_gemini(items, target_words)

    # 2) save raw script for debugging / inspection
    raw_script_path = os.path.join(EPISODES_DIR, "episode_script_raw.txt")
    with open(raw_script_path, "w") as f:
        f.write(script)
    print(f"Raw script saved to {raw_script_path}")

    # 3) advanced postprocessing for TTS
    clean_script = postprocess_for_tts_plain(script)

    # 4) save cleaned script too
    clean_script_path = os.path.join(EPISODES_DIR, "episode_script_clean.txt")
    with open(clean_script_path, "w") as f:
        f.write(clean_script)
    print(f"Cleaned script saved to {clean_script_path}")

    # 5) convert cleaned script to audio
    out_file = os.path.join(EPISODES_DIR, f"episode_{timestamp}.mp3")
    text_to_speech(clean_script, out_file)
    
    # 5.5) Save metadata (duration arg) for RSS generation
    meta_file = os.path.join(EPISODES_DIR, f"episode_metadata_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump({"duration_minutes": args.duration}, f)
    print(f"Saved metadata to {meta_file}")
    
    # 6) Generate RSS feed (SKIP if in test mode)
    if not args.test:
        cleanup_old_episodes()
        generate_rss_feed()
    else:
        print("Test mode: Skipping RSS feed generation.")

    print("\n=== Done! ===")



if __name__ == "__main__":
    main()

