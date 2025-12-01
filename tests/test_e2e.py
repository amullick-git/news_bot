import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import shutil

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import podcast_bot

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        # Clean up test_episodes before run
        if os.path.exists("test_episodes"):
            shutil.rmtree("test_episodes")

    def tearDown(self):
        # Clean up after run
        if os.path.exists("test_episodes"):
            shutil.rmtree("test_episodes")

    @patch('sys.argv', ['podcast_bot.py', '--test', '--duration', '5'])
    @patch('podcast_bot.texttospeech.TextToSpeechClient')
    @patch('podcast_bot.genai.GenerativeModel')
    @patch('podcast_bot.fetch_all')
    def test_full_flow(self, mock_fetch, mock_genai_model, mock_tts_client):
        # 1. Mock RSS Data
        mock_fetch.return_value = [
            {
                "title": "Test News 1", 
                "summary": "Summary 1", 
                "link": "http://test.com/1", 
                "published": "Sun, 01 Dec 2025 10:00:00 GMT"
            },
            {
                "title": "Test News 2", 
                "summary": "Summary 2", 
                "link": "http://test.com/2", 
                "published": "Sun, 01 Dec 2025 09:00:00 GMT"
            },
        ]

        # 2. Mock Gemini Response
        # genai.GenerativeModel("...") returns a model object
        mock_model_instance = MagicMock()
        mock_genai_model.return_value = mock_model_instance
        
        # Response 1: Semantic Filtering (JSON list of indices)
        mock_response_filter = MagicMock()
        mock_response_filter.text = "[0, 1]"
        
        # Response 2: Script Generation (Dialogue)
        mock_response_script = MagicMock()
        mock_response_script.text = """
HOST: Welcome to the test news.
REPORTER: Here is the first story about Test News 1.
HOST: Interesting. What else?
REPORTER: Test News 2 happened today.
HOST: Thanks. Goodbye.
"""
        
        # Set side_effect to return different responses in order
        mock_model_instance.generate_content.side_effect = [mock_response_filter, mock_response_script]

        # 3. Mock TTS Response
        # texttospeech.TextToSpeechClient() returns a client
        mock_client_instance = MagicMock()
        mock_tts_client.return_value = mock_client_instance
        
        mock_audio_resp = MagicMock()
        mock_audio_resp.audio_content = b"fake_audio_data"
        mock_client_instance.synthesize_speech.return_value = mock_audio_resp

        # 4. Run Main
        podcast_bot.main()

        # 5. Verify Artifacts
        self.assertTrue(os.path.exists("test_episodes"), "test_episodes dir not created")
        
        # Check for MP3
        files = os.listdir("test_episodes")
        mp3_files = [f for f in files if f.endswith(".mp3")]
        self.assertTrue(len(mp3_files) > 0, "No MP3 file created")
        
        # Check for script
        self.assertTrue(os.path.exists("test_episodes/episode_script_clean.txt"))
        
        # Verify mocks were called
        mock_fetch.assert_called_once()
        mock_model_instance.generate_content.assert_called()
        mock_client_instance.synthesize_speech.assert_called()

if __name__ == '__main__':
    unittest.main()
