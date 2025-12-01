import pytest
import sys
import os
from datetime import datetime

# Add parent directory to path to import podcast_bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.podcast_bot import (
    strip_markdown_formatting,
    remove_stage_directions,
    ensure_sentence_punctuation,
    collapse_whitespace,
    parse_published_date
)

def test_strip_markdown_formatting():
    text = """
    # Headline
    **Bold text**
    * Bullet point
    1. Numbered list
    """
    cleaned = strip_markdown_formatting(text)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "1." not in cleaned
    assert "Headline" in cleaned
    assert "Bold text" in cleaned

def test_remove_stage_directions():
    text = """
    HOST: Hello world.
    (Music fades in)
    REPORTER: Here is the news.
    [Applause]
    *laughs*
    """
    cleaned = remove_stage_directions(text)
    assert "(Music fades in)" not in cleaned
    assert "[Applause]" not in cleaned
    assert "*laughs*" not in cleaned
    assert "HOST: Hello world." in cleaned

def test_ensure_sentence_punctuation():
    text = "This is a sentence\nThis is another one.\nShort"
    cleaned = ensure_sentence_punctuation(text)
    lines = cleaned.split('\n')
    assert lines[0].strip() == "This is a sentence."
    assert lines[1].strip() == "This is another one."
    assert lines[2].strip() == "Short" # Short lines skipped

def test_collapse_whitespace():
    text = "Line 1\n\n\nLine 2   with   spaces"
    cleaned = collapse_whitespace(text)
    assert "\n\n\n" not in cleaned
    assert cleaned == "Line 1\n\nLine 2 with spaces"

def test_parse_published_date():
    # Test RFC822 date
    rfc_date = "Sun, 30 Nov 2025 08:00:00 +0000"
    dt = parse_published_date(rfc_date)
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 11
    assert dt.day == 30

    # Test invalid date
    assert parse_published_date("Invalid Date") is None
