import pytest
from unittest.mock import patch, MagicMock
from src import main as src_main
from src.notification import EpisodeInfo
import os

@patch('src.main.setup_logging')
@patch('src.main.load_config')
@patch('src.main.fetch_all')
@patch('src.main.archive')
@patch('src.main.filter_by_time_window')
@patch('src.main.configure_gemini')
@patch('src.local_ai.LocalFilter')
@patch('src.content.filter_by_semantics')
@patch('src.main.summarize_with_gemini')
@patch('src.main.postprocess_for_tts_plain')
@patch('src.main.text_to_speech')
@patch('src.main.generate_rss_feed')
@patch('src.main.cleanup_old_episodes')
@patch('src.main.archive.cleanup_archive')
@patch('src.main.generate_episode_links_page')
@patch('src.main.update_index_with_links')
@patch('src.metrics.MetricsLogger')
@patch('src.main.send_notification')
def test_notification_stats_logic(
    mock_send, mock_metrics, mock_update, mock_links, mock_clean_archive, mock_clean_eps, mock_rss, 
    mock_tts, mock_post, mock_sum, mock_gemini_filter, mock_local_ai_cls, mock_gemini_config, 
    mock_time_filter, mock_archive, mock_fetch, mock_config_loader, mock_log
):
    # Setup Config
    mock_config = MagicMock()
    mock_config.feeds = {"general": ["http://test.com"]}
    mock_config.keywords = {"general": ["keyword"]} # Enables Stage 1
    mock_config.processing.local_prefilter_limit = 10
    mock_config.processing.max_final_articles = 5
    mock_config.processing.duration_minutes = 5
    mock_config.processing.words_per_min = 100
    mock_config.processing.gemini_model = "model"
    mock_config.processing.voice_type = "voice"
    mock_config.processing.max_parallel_tts_calls = 1
    mock_config.processing.retention_days = 7
    mock_config.podcast.episodes_dir = "episodes"
    mock_config.podcast.base_url = "http://base"
    mock_config.notification.enabled = True
    
    mock_config_loader.return_value = mock_config

    # Setup Data Flow
    # 1. Fetched
    item1 = {"title": "A", "link": "http://nyt.com/1", "source_name": "NYT"}
    item2 = {"title": "B", "link": "http://bbc.com/1", "source_name": "BBC"}
    item3 = {"title": "C", "link": "http://nyt.com/2", "source_name": "NYT"}
    fetched = [item1, item2, item3]
    mock_fetch.return_value = fetched
    mock_time_filter.return_value = fetched

    # 2. Local Filter (Stage 1) - Drop BBC
    mock_local_instance = mock_local_ai_cls.return_value
    candidates = [item1, item3] # Only NYT passed
    mock_local_instance.filter_by_relevance.return_value = candidates

    # 3. Gemini Filter (Stage 2) - Drop one NYT
    final_items = [item1] 
    mock_gemini_filter.return_value = final_items
    
    # 4. Summarize
    mock_sum.return_value = "Script"
    mock_post.return_value = "Clean Script"

    # Run Main with args
    with patch('sys.argv', ['main.py', '--type', 'general_daily', '--duration', '5']):
        # We need to mock os.makedirs and open to avoid file IO errors
        with patch('os.makedirs'), patch('builtins.open', MagicMock()):
            src_main.main()

    # Verify Notification
    assert mock_send.call_count == 1
    call_args = mock_send.call_args
    # args[0] is config
    # args[1] is EpisodeInfo
    episode_info = call_args[0][1]
    
    stats = episode_info.metrics_summary
    print(stats)

    # Check for 3-stage header
    assert "Fetched ➔ S1 ➔ Final" in stats
    
    # Check Counts
    # NYT: Fetched 2, S1 2, Final 1 -> "2 ➔ 2 ➔ 1"
    assert "NYT: 2 ➔ 2 ➔ 1" in stats
    
    # BBC: Fetched 1, S1 0, Final 0 -> "1 ➔ 0 ➔ 0"
    assert "BBC: 1 ➔ 0 ➔ 0" in stats
