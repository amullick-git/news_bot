import unittest
import sys
import os
from datetime import datetime

# Add parent directory to path to import podcast_bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from podcast_bot import (
    strip_markdown_formatting,
    remove_stage_directions,
    ensure_sentence_punctuation,
    collapse_whitespace,
    parse_published_date
)

class TestPodcastBot(unittest.TestCase):
    def test_strip_markdown_formatting(self):
        text = """
        # Headline
        **Bold text**
        * Bullet point
        1. Numbered list
        """
        cleaned = strip_markdown_formatting(text)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("1.", cleaned)
        self.assertIn("Headline", cleaned)
        self.assertIn("Bold text", cleaned)

    def test_remove_stage_directions(self):
        text = """
        HOST: Hello world.
        (Music fades in)
        REPORTER: Here is the news.
        [Applause]
        *laughs*
        """
        cleaned = remove_stage_directions(text)
        self.assertNotIn("(Music fades in)", cleaned)
        self.assertNotIn("[Applause]", cleaned)
        self.assertNotIn("*laughs*", cleaned)
        self.assertIn("HOST: Hello world.", cleaned)

    def test_ensure_sentence_punctuation(self):
        text = "This is a sentence\nThis is another one.\nShort"
        cleaned = ensure_sentence_punctuation(text)
        lines = cleaned.split('\n')
        self.assertEqual(lines[0].strip(), "This is a sentence.")
        self.assertEqual(lines[1].strip(), "This is another one.")
        self.assertEqual(lines[2].strip(), "Short") # Short lines skipped

    def test_collapse_whitespace(self):
        text = "Line 1\n\n\nLine 2   with   spaces"
        cleaned = collapse_whitespace(text)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertEqual(cleaned, "Line 1\n\nLine 2 with spaces")

    def test_parse_published_date(self):
        # Test RFC822 date
        rfc_date = "Sun, 30 Nov 2025 08:00:00 +0000"
        dt = parse_published_date(rfc_date)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 30)

        # Test invalid date
        self.assertIsNone(parse_published_date("Invalid Date"))

if __name__ == '__main__':
    unittest.main()
