import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Ensure scripts dir is in path so we can import the script module
sys.path.append(os.path.join(os.getcwd(), "scripts"))

import regenerate_feed

def test_regenerate_feed_success():
    with patch("regenerate_feed.setup_logging") as mock_setup, \
         patch("regenerate_feed.get_logger") as mock_get_logger, \
         patch("regenerate_feed.load_config") as mock_load_config, \
         patch("regenerate_feed.generate_rss_feed") as mock_generate:
         
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        regenerate_feed.main()
        
        mock_setup.assert_called_once()
        mock_load_config.assert_called_once()
        mock_generate.assert_called_once()
        mock_logger.info.assert_any_call("Regenerating RSS feed...")
        mock_logger.info.assert_any_call("Feed regeneration complete.")

def test_regenerate_feed_failure():
    with patch("regenerate_feed.setup_logging"), \
         patch("regenerate_feed.get_logger") as mock_get_logger, \
         patch("regenerate_feed.load_config") as mock_load_config, \
         patch("regenerate_feed.generate_rss_feed") as mock_generate, \
         patch("sys.exit") as mock_exit:
         
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Simulate an error
        mock_generate.side_effect = Exception("Boom")
        
        regenerate_feed.main()
        
        mock_logger.error.assert_called_with("Failed to regenerate feed: Boom")
        mock_exit.assert_called_once_with(1)
