import html
import re
import os
import feedparser
import textwrap
from datetime import datetime
from textwrap import dedent
from urllib.parse import urlparse
from datetime import datetime, timedelta
import email.utils as email_date_parser   # parses RFC822 dates



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
    "image": "https://placehold.co/1400x1400/png?text=News+Podcast", # Replace with a real URL
    "language": "en"
}


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

def summarize_with_gemini(articles):
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
You are writing a script for a professional news anchor.

Produce a single monologue for a news update broadcast.

**Tone & Style Requirements:**
- Strictly factual, concise, and neutral.
- No opinions, no moralizing, no motivational language.
- No commentary such as “this is important” or “let’s dive in.”
- No rhetorical questions.
- No transitions like “meanwhile,” “in other news,” “let’s turn to.”
- Just clean, newsroom-style delivery.
- Prioritize clarity over charm.
- Use short sentences. Keep paragraphs tight.
- Use neutral broadcast phrasing like: “According to X”, “The company said”, "Officials reported".

**Structure Requirements:**
- Short, clean introduction (1–2 sentences): identify that this is a news update.
- For each story:
  - Start with the headline distilled into one short sentence.
  - Follow with the essential facts only.
- No stage directions or sound cues.
- No URLs.
- No mention of being an AI.

**Length Target:**
About {TARGET_WORDS} words.

**Stories:**
{articles_block}

Now produce the script.
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

def chunk_text_for_tts(text, max_bytes=4500):
    """
    Split text into chunks so that each chunk is under max_bytes when UTF-8 encoded.
    We try to split on paragraph boundaries, then sentences if needed.
    """
    import re

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    def byte_len(s):
        return len(s.encode("utf-8"))

    for para in paragraphs:
        if not current:
            # start a new chunk
            if byte_len(para) <= max_bytes:
                current = para
            else:
                # paragraph itself too big – split by sentences
                sentences = re.split(r'(?<=[.!?]) +', para)
                temp = ""
                for s in sentences:
                    if not s:
                        continue
                    candidate = (temp + " " + s).strip() if temp else s
                    if byte_len(candidate) > max_bytes:
                        if temp:
                            chunks.append(temp)
                        temp = s
                    else:
                        temp = candidate
                if temp:
                    chunks.append(temp)
                current = ""
        else:
            candidate = current + "\n\n" + para
            if byte_len(candidate) <= max_bytes:
                current = candidate
            else:
                chunks.append(current)
                # start new chunk with this paragraph (may need further split)
                if byte_len(para) <= max_bytes:
                    current = para
                else:
                    # again split long paragraph into sentences
                    sentences = re.split(r'(?<=[.!?]) +', para)
                    temp = ""
                    for s in sentences:
                        if not s:
                            continue
                        c2 = (temp + " " + s).strip() if temp else s
                        if byte_len(c2) > max_bytes:
                            if temp:
                                chunks.append(temp)
                            temp = s
                        else:
                            temp = c2
                    if temp:
                        chunks.append(temp)
                    current = ""
    if current:
        chunks.append(current)

    return chunks

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
        return "medium", 900   # steady, slightly longer pause
    if kind == "outro":
        return "slow", 1000    # calmer ending
    if kind == "short":
        return "fast", 500     # quick little lines
    if kind == "long":
        return "medium", 800   # don't rush long paragraphs
    # normal
    return "medium", 600


def build_ssml_from_chunk(chunk: str) -> str:
    """
    Turn a cleaned text chunk into SSML with dynamic pacing:
    - classify each paragraph
    - wrap in <prosody rate="...">
    - add <break> with different times between paragraphs
    """
    # treat double newlines as paragraph breaks
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', chunk) if p.strip()]

    ssml_parts = []

    for idx, p in enumerate(paragraphs):
        kind = classify_paragraph(p)
        rate, break_ms = pacing_for_type(kind)

        escaped = html.escape(p)
        ssml_parts.append(f'<p><prosody rate="{rate}">{escaped}</prosody></p>')

        # add a pause after every paragraph except the last one
        if idx != len(paragraphs) - 1:
            ssml_parts.append(f'<break time="{break_ms}ms"/>')

    ssml_body = "\n".join(ssml_parts)
    return f"<speak>\n{ssml_body}\n</speak>"

from google.cloud import texttospeech

def text_to_speech(clean_script, output_file="episode.mp3"):
    print("\n=== Converting to speech using Google TTS (dynamic SSML + chunked)… ===")

    client = texttospeech.TextToSpeechClient()

    # Split cleaned plain text into safe chunks
    chunks = chunk_text_for_tts(clean_script, max_bytes=4500)
    print(f"Total chunks: {len(chunks)}")

    audio_contents = []

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        # you can switch to Neural2 or another voice here
        name="en-US-Neural2-F",
    )

    # Let SSML handle local pacing; keep global rate at 1.2
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.3,   # base rate; SSML <prosody rate="..."> adjusts per paragraph
        pitch=0.0,
        volume_gain_db=0.0,
    )

    for idx, chunk in enumerate(chunks, 1):
        print(f"  Synthesizing chunk {idx}/{len(chunks)}…")

        ssml = build_ssml_from_chunk(chunk)
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml)

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        audio_contents.append(response.audio_content)

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
    fg.podcast.itunes_category('News')
    
    # Find all generated MP3 episodes
    # Assuming format: episode_YYYY-MM-DD.mp3
    episode_files = sorted(glob.glob("episode_*.mp3"), reverse=True)
    
    for mp3_file in episode_files:
        # Parse date from filename
        try:
            # filename example: episode_2025-11-30_15.mp3 or episode_2025-11-30.mp3
            date_str = mp3_file.replace("episode_", "").replace(".mp3", "")
            
            # Try parsing with hour first
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d_%H")
                display_title = dt.strftime("%Y-%m-%d %H:00")
            except ValueError:
                # Fallback to day only
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                display_title = date_str
                
            # Make it timezone aware (UTC) for the feed
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            print(f"Skipping file with unexpected name format: {mp3_file}")
            continue
            
        file_size = os.path.getsize(mp3_file)
        file_url = f"{BASE_URL}/{mp3_file}"
        
        fe = fg.add_entry()
        fe.id(file_url)
        fe.title(f"News Briefing: {display_title}")
        fe.description(f"Daily news summary for {display_title}.")
        fe.enclosure(file_url, str(file_size), 'audio/mpeg')
        fe.published(dt)
        
    fg.rss_file('feed.xml')
    print("Generated feed.xml")




###########################################
# MAIN PIPELINE
###########################################

def main():
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

    # write a file listing the chosen stories for this episode
    # Include hour in timestamp to allow multiple runs per day
    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    sources_file = f"episode_sources_{timestamp}.md"
    write_episode_sources(items, sources_file)

    # 1) produce the raw script from Gemini
    script = summarize_with_gemini(items)

    # 2) save raw script for debugging / inspection
    with open("episode_script_raw.txt", "w") as f:
        f.write(script)
    print("Raw script saved to episode_script_raw.txt")

    # 3) advanced postprocessing for TTS
    clean_script = postprocess_for_tts_plain(script)

    # 4) save cleaned script too
    with open("episode_script_clean.txt", "w") as f:
        f.write(clean_script)
    print("Cleaned script saved to episode_script_clean.txt")

    # 5) convert cleaned script to audio
    out_file = f"episode_{timestamp}.mp3"
    text_to_speech(clean_script, out_file)
    
    # 6) Generate RSS feed
    generate_rss_feed()

    print("\n=== Done! ===")



if __name__ == "__main__":
    main()

