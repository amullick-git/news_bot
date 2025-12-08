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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def make_ssml_paragraph(text: str) -> str:
    escaped = html.escape(text)
    escaped = escaped.replace(", ", '<break strength="weak"/> ')
    return f'<p>{escaped}</p><break time="500ms"/>'

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

def generate_plain_chunks(text: str, max_bytes=5000) -> list[str]:
    """
    Chunk text for TTS without SSML tags (for Chirp/Journey voices).
    """
    raw_paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    flat_paragraphs = []
    for p in raw_paragraphs:
        if len(p) > 2000:
             sentences = re.split(r'(?<=[.!?]) +', p)
             flat_paragraphs.extend([s for s in sentences if s])
        else:
            flat_paragraphs.append(p)
            
    chunks = []
    current_chunk = ""
    current_size = 0
    
    for p in flat_paragraphs:
        # Just use the raw text, maybe add double newline for pauses if needed
        # But for plain text TTS, punctuation dictates pauses.
        part_content = p + "\n\n"
        part_len = len(part_content.encode("utf-8"))
        
        if part_len > max_bytes:
             logger.warning(f"Dropping a paragraph that exceeds {max_bytes} bytes.")
             continue

        if current_size + part_len > max_bytes:
            chunks.append(current_chunk.strip())
            current_chunk = part_content
            current_size = part_len
        else:
            current_chunk += part_content
            current_size += part_len
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def synthesize_chunk(client, synthesis_input, voice, audio_config):
    return client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

def text_to_speech(clean_script: str, output_file: str, voice_type: str = "wavenet", max_parallel_calls: int = 5):
    logger.info(f"Converting to speech using Google TTS ({voice_type})...")

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
    total_chars = 0

    # Voice Definitions
    # D = Male, F = Female (usually)
    if voice_type == "neural":
        host_name = "en-US-Neural2-D"
        reporter_name = "en-US-Neural2-F"
    elif voice_type == "studio":
        # Studio voices are premium: M (Male), O (Female) are common high-quality ones
        host_name = "en-US-Studio-M"
        reporter_name = "en-US-Studio-O"
    elif voice_type == "chirp3-hd":
        # Chirp 3 HD Voices (USM v3)
        # Using named voices: Fenrir (Male) and Kore (Female)
        host_name = "en-US-Chirp3-HD-Fenrir"
        reporter_name = "en-US-Chirp3-HD-Kore"
    else: # wavenet (default)
        host_name = "en-US-Wavenet-D"
        reporter_name = "en-US-Wavenet-F"

    # Process segments
    
    # 1. PREPARATION PHASE: Generate all chunks
    all_tasks = []
    
    for i, (speaker, text_content) in enumerate(segments):
        # Select voice
        voice_name = host_name if speaker == "HOST" else reporter_name
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice_name
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.15
        )

        # Generate chunks (SSML or Plain Text)
        chunks = generate_ssml_chunks(text_content)
        is_ssml = True
        
        for chunk_idx, chunk in enumerate(chunks):
            all_tasks.append({
                "seg_idx": i,
                "chunk_idx": chunk_idx,
                "chunk": chunk,
                "is_ssml": is_ssml,
                "voice_params": voice_params,
                "audio_config": audio_config,
                "speaker": speaker
            })

    # Helper function for parallel synthesis
    def synthesize_task(task):
        """Synthesize a single task and return (seg_idx, chunk_idx, audio_content, char_count)"""
        seg_idx = task["seg_idx"]
        chunk_idx = task["chunk_idx"]
        chunk = task["chunk"]
        
        if task["is_ssml"]:
            synthesis_input = texttospeech.SynthesisInput(ssml=chunk)
        else:
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
        
        try:
            response = synthesize_chunk(client, synthesis_input, task["voice_params"], task["audio_config"])
            char_count = len(chunk)
            logger.debug(f"  Segment {seg_idx} Chunk {chunk_idx} synthesized ({char_count} chars)")
            return (seg_idx, chunk_idx, response.audio_content, char_count)
        except Exception as e:
            logger.error(f"Failed to synthesize Segment {seg_idx}-Chunk {chunk_idx}: {e}")
            raise e
    
    # 2. EXECUTION PHASE: Run all tasks in parallel
    logger.info(f"Synthesizing {len(all_tasks)} total chunks with {max_parallel_calls} parallel workers...")
    
    chunk_results = {} # Key: (seg_idx, chunk_idx)
    import time
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_parallel_calls) as executor:
        # Submit all tasks
        futures = {
            executor.submit(synthesize_task, task): task
            for task in all_tasks
        }
        
        # Collect results
        for future in as_completed(futures):
            seg_idx, chunk_idx, audio_content, char_count = future.result()
            chunk_results[(seg_idx, chunk_idx)] = (audio_content, char_count)
            total_chars += char_count

    elapsed = time.time() - start_time
    logger.info(f"Global parallel synthesis completed in {elapsed:.2f}s ({len(all_tasks)} chunks)")

    # 3. ASSEMBLY PHASE: Concatenate in order
    # Sort keys by seg_idx then chunk_idx
    sorted_keys = sorted(chunk_results.keys())
    
    for key in sorted_keys:
        audio_contents.append(chunk_results[key][0])

    with open(output_file, "wb") as out:
        for content in audio_contents:
            out.write(content)

    logger.info(f"Saved audio file: {output_file}")
    return total_chars
