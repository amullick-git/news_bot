import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import shutil

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.podcast_bot as podcast_bot

@pytest.fixture
def cleanup_episodes():
    # Setup: Clean before
    if os.path.exists("test_episodes"):
        shutil.rmtree("test_episodes")
    yield
    # Teardown: Clean after
    if os.path.exists("test_episodes"):
        shutil.rmtree("test_episodes")

@patch('sys.argv', ['src/podcast_bot.py', '--test', '--duration', '5'])
@patch('src.podcast_bot.texttospeech.TextToSpeechClient')
@patch('src.podcast_bot.genai.GenerativeModel')
@patch('src.podcast_bot.fetch_all')
def test_full_flow(mock_fetch, mock_genai_model, mock_tts_client, cleanup_episodes):
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
    assert os.path.exists("test_episodes"), "test_episodes dir not created"
    
    # Check for MP3
    files = os.listdir("test_episodes")
    mp3_files = [f for f in files if f.endswith(".mp3")]
    assert len(mp3_files) > 0, "No MP3 file created"
    
    # Check for script
    assert os.path.exists("test_episodes/episode_script_clean.txt")
    
    # Check for metadata
    import json
    json_files = [f for f in files if f.startswith("episode_metadata_") and f.endswith(".json")]
    assert len(json_files) > 0, "No metadata file created"
    
    with open(os.path.join("test_episodes", json_files[0]), "r") as f:
        meta = json.load(f)
        assert meta["duration_minutes"] == 5
    
    # Verify mocks were called
    mock_fetch.assert_called_once()
    mock_model_instance.generate_content.assert_called()
    mock_client_instance.synthesize_speech.assert_called()
