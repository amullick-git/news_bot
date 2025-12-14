import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytest

# Add src to path if needed (pytest usually handles this if run from root)
# from src.main import main

@patch("src.main.cleanup_old_episodes")
@patch("src.main.generate_rss_feed")
@patch("src.main.summarize_with_gemini")
@patch("src.main.filter_by_semantics")
@patch("src.main.filter_by_time_window")
@patch("src.main.fetch_all")
@patch("src.main.load_config")
@patch("src.main.write_episode_sources") # Mock file writing
@patch("src.main.postprocess_for_tts_plain")
@patch("src.main.text_to_speech")
@patch("builtins.open", new_callable=MagicMock) # Mock file opening
@patch("src.main.json.dump") # Mock json dump
@patch("os.makedirs")
def test_greeting_morning(mock_makedirs, mock_json_dump, mock_open, mock_tts, mock_postprocess, mock_write_sources, mock_config, mock_fetch, mock_time_filter, mock_filter, mock_summarize, mock_rss, mock_cleanup):
    from src.main import main
    
    # Setup mocks
    config_mock = MagicMock()
    config_mock.keywords = {"general": []}
    config_mock.feeds = {"general": ["http://mock.feed"]}
    config_mock.processing.duration_minutes = 5
    config_mock.processing.words_per_min = 150
    config_mock.processing_overrides = {}
    config_mock.podcast.episodes_dir = "test_output/docs/episodes"
    config_mock.processing.gemini_model = "gemini-pro"
    config_mock.processing.voice_type = "neural" # explicit string
    config_mock.processing.retention_days = 7
    config_mock.source_limits = {}
    mock_config.return_value = config_mock

    # Mock Data
    mock_fetch.return_value = [{"title": "Technology Update", "link": "http://example.com", "summary": "Tech news"}]
    mock_time_filter.side_effect = lambda items, **kwargs: items
    mock_filter.return_value = [{"title": "Technology Update", "link": "http://example.com", "summary": "Tech news"}]
    mock_summarize.return_value = "Script with greeting"
    
    # Run main with test args for Morning (10 AM)
    with patch("sys.argv", ["main.py", "--test", "--no-tts", "--type", "general_daily"]):
        with patch("src.main.datetime") as mock_datetime:
            mock_datetime.now.return_value.hour = 10
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01_10"
            
            main()
            
            # Verify greeting passed to summarize_with_gemini
            call_args = mock_summarize.call_args
            assert call_args is not None
            _, kwargs = call_args
            assert kwargs.get('greeting') == "Good Morning"

@patch("src.main.cleanup_old_episodes")
@patch("src.main.generate_rss_feed")
@patch("src.main.summarize_with_gemini")
@patch("src.main.filter_by_semantics")
@patch("src.main.filter_by_time_window")
@patch("src.main.fetch_all")
@patch("src.main.load_config")
@patch("src.main.write_episode_sources")
@patch("src.main.postprocess_for_tts_plain")
@patch("src.main.text_to_speech")
@patch("builtins.open", new_callable=MagicMock)
@patch("src.main.json.dump")
@patch("os.makedirs")
def test_greeting_evening(mock_makedirs, mock_json_dump, mock_open, mock_tts, mock_postprocess, mock_write_sources, mock_config, mock_fetch, mock_time_filter, mock_filter, mock_summarize, mock_rss, mock_cleanup):
    from src.main import main

    # Setup mocks (same as above)
    config_mock = MagicMock()
    config_mock.keywords = {"general": []}
    config_mock.feeds = {"general": ["http://mock.feed"]}
    config_mock.processing.duration_minutes = 5
    config_mock.processing.words_per_min = 150
    config_mock.processing_overrides = {}
    config_mock.podcast.episodes_dir = "test_output/docs/episodes"
    config_mock.processing.gemini_model = "gemini-pro"
    config_mock.processing.voice_type = "neural"
    config_mock.processing.retention_days = 7
    config_mock.source_limits = {}
    mock_config.return_value = config_mock

    mock_fetch.return_value = [{"title": "Technology Update", "link": "http://example.com"}]
    mock_time_filter.side_effect = lambda items, **kwargs: items
    mock_filter.return_value = [{"title": "Technology Update", "link": "http://example.com"}]
    mock_summarize.return_value = "Script with greeting"
    
    # Run main with test args for Evening (19 PM)
    with patch("sys.argv", ["main.py", "--test", "--no-tts", "--type", "general_daily"]):
        with patch("src.main.datetime") as mock_datetime:
            mock_datetime.now.return_value.hour = 19
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01_19"
            
            main()
            
            call_args = mock_summarize.call_args
            assert call_args is not None
            _, kwargs = call_args
            assert kwargs.get('greeting') == "Good Evening"
