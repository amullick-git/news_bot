"""
Audio Synthesis (TTS)
=====================

This module manages the conversion of text scripts into audio files using Google Cloud Text-to-Speech.
Key features:
- SSML generation for controlling prosody and breaks.
- Multi-speaker support (Host vs. Reporter).
- Smart chunking of text to respect API limits.
- Audio segment concatenation.
"""
import re
import html
from textwrap import dedent
from google.cloud import texttospeech
from tenacity import retry, stop_after_attempt, wait_exponential
from .utils import get_logger

logger = get_logger(__name__)

STAGE_DIRECTION_PATTERNS = [
    r'\([^)]*\)',          # (Intro music), (SFX: boom), etc.
    r'\[[^\]]*\]',         # [Soft music], [Applause], etc.
    r'\*[^*]*\*',          # *applause*, *laughs*, *emphasis*
]

def remove_stage_directions(text: str) -> str:
    for pat in STAGE_DIRECTION_PATTERNS:
        text = re.sub(pat, '', text)

    text = re.sub(
        r'^(?:sfx|fx|music|sound|audio)\s*[:\-].*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    text = re.sub(
        r'^\s*(intro|outro|background)\s+music.*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    return text

def strip_markdown_formatting(text: str) -> str:
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
    text = text.replace('**', '').replace('__', '')
    return text

def collapse_whitespace(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split('\n')]
    cleaned_lines = []
    for line in lines:
        if line:
            cleaned_lines.append(line)
        else:
            cleaned_lines.append('')
    return '\n'.join(cleaned_lines).strip()

def ensure_sentence_punctuation(text: str) -> str:
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append('')
            continue

        if stripped[-1] in '.?!':
            new_lines.append(stripped)
            continue

        if len(stripped.split()) <= 2:
            new_lines.append(stripped)
            continue

        new_lines.append(stripped + '.')
    return '\n'.join(new_lines)

def flatten_for_tts(text: str) -> str:
    text = dedent(text).strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def postprocess_for_tts_plain(raw_script: str) -> str:
    text = raw_script
    text = remove_stage_directions(text)
    text = strip_markdown_formatting(text)
    text = collapse_whitespace(text)
    text = ensure_sentence_punctuation(text)
    text = flatten_for_tts(text)
    return text

def classify_paragraph(p: str) -> str:
    pl = p.strip().lower()
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
    if kind == "intro":
        return "fast", 900
    if kind == "outro":
        return "medium", 600
    if kind == "short":
        return "fast", 500
    if kind == "long":
        return "fast", 800
    return "medium", 600

def make_ssml_paragraph(text: str) -> str:
    kind = classify_paragraph(text)
    rate, break_ms = pacing_for_type(kind)
    escaped = html.escape(text)
    escaped = escaped.replace(", ", '<break strength="weak"/> ')
    return f'<p><prosody rate="{rate}">{escaped}</prosody></p><break time="{break_ms}ms"/>'

def generate_ssml_chunks(text: str, max_bytes=5000) -> list[str]:
    raw_paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    flat_paragraphs = []
    for p in raw_paragraphs:
        if len(p) > 2000: 
             sentences = re.split(r'(?<=[.!?]) +', p)
             flat_paragraphs.extend([s for s in sentences if s])
        else:
            flat_paragraphs.append(p)
            
    chunks = []
    wrapper_overhead = len("<speak>\n\n</speak>")
    current_chunk_ssml = ""
    current_size = wrapper_overhead
    
    for p in flat_paragraphs:
        ssml_part = make_ssml_paragraph(p)
        part_len = len(ssml_part.encode("utf-8"))
        
        if part_len + wrapper_overhead > max_bytes:
            logger.warning(f"Dropping a paragraph that exceeds {max_bytes} bytes even alone.")
            continue
            
        if current_size + part_len > max_bytes:
            chunks.append(f"<speak>\n{current_chunk_ssml}\n</speak>")
            current_chunk_ssml = ssml_part
            current_size = wrapper_overhead + part_len
        else:
            if current_chunk_ssml:
                current_chunk_ssml += "\n"
            current_chunk_ssml += ssml_part
            current_size += part_len + 1
            
    if current_chunk_ssml:
        chunks.append(f"<speak>\n{current_chunk_ssml}\n</speak>")
        
    return chunks

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def synthesize_chunk(client, synthesis_input, voice, audio_config):
    return client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

def text_to_speech(clean_script: str, output_file: str):
    logger.info("Converting to speech using Google TTS...")

    client = texttospeech.TextToSpeechClient()

    segments = []
    current_speaker = "HOST"
    current_text = []
    
    lines = clean_script.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("HOST:"):
            if current_speaker == "REPORTER" and current_text:
                segments.append(("REPORTER", "\n".join(current_text)))
                current_text = []
            current_speaker = "HOST"
            content = line.replace("HOST:", "").strip()
            if content:
                current_text.append(content)
                
        elif line.startswith("REPORTER:"):
            if current_speaker == "HOST" and current_text:
                segments.append(("HOST", "\n".join(current_text)))
                current_text = []
            current_speaker = "REPORTER"
            content = line.replace("REPORTER:", "").strip()
            if content:
                current_text.append(content)
        else:
            current_text.append(line)
            
    if current_text:
        segments.append((current_speaker, "\n".join(current_text)))

    logger.info(f"Parsed {len(segments)} dialogue segments.")

    audio_contents = []

    voice_host = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D", 
    )
    voice_reporter = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-F", 
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.2,
        pitch=0.0,
        volume_gain_db=0.0,
    )

    for idx, (speaker, text) in enumerate(segments, 1):
        logger.debug(f"Synthesizing segment {idx}/{len(segments)} ({speaker})...")
        
        ssml_chunks = generate_ssml_chunks(text, max_bytes=4800)
        voice = voice_host if speaker == "HOST" else voice_reporter
        
        for ssml in ssml_chunks:
            synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
            try:
                response = synthesize_chunk(client, synthesis_input, voice, audio_config)
                audio_contents.append(response.audio_content)
            except Exception as e:
                logger.error(f"Error synthesizing chunk: {e}")
                raise

    with open(output_file, "wb") as out:
        for content in audio_contents:
            out.write(content)

    logger.info(f"Saved audio file: {output_file}")
