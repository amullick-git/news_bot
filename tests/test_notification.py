
import pytest
from unittest.mock import patch, MagicMock
from src.notification import send_notification, EpisodeInfo, _send_discord, _send_slack
from src.config import Config, NotificationConfig, ProcessingConfig, PodcastConfig

@pytest.fixture
def mock_config():
    return Config(
        feeds={}, keywords={},
        processing=ProcessingConfig(duration_minutes=10, words_per_min=100, max_per_feed=5, max_final_articles=5, retention_days=100),
        podcast=PodcastConfig(base_url="http://test", title="Show", author="Me", image_filename="img.jpg", language="en", episodes_dir="docs/episodes"),
        notification=NotificationConfig(enabled=True, platform="discord")
    )

@pytest.fixture
def episode_info():
    return EpisodeInfo(
        title="Test Episode",
        mp3_url="http://test/ep.mp3",
        links_url="http://test/links.html",
        cover_image_url="http://test/img.jpg"
    )

def test_notification_disabled(mock_config, episode_info):
    mock_config.notification.enabled = False
    with patch("src.notification.requests.post") as mock_post:
        send_notification(mock_config, episode_info)
        mock_post.assert_not_called()

def test_notification_no_webhook(mock_config, episode_info, monkeypatch):
    monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
    with patch("src.notification.requests.post") as mock_post:
        send_notification(mock_config, episode_info)
        mock_post.assert_not_called()

def test_discord_notification(mock_config, episode_info, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "http://discord/webhook")
    mock_config.notification.platform = "discord"
    
    with patch("src.notification.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        send_notification(mock_config, episode_info)
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://discord/webhook"
        payload = kwargs['json']
        assert payload['username'] == "News Bot"
        assert len(payload['embeds']) == 1
        assert payload['embeds'][0]['title'] == "🎙️ New Episode: Test Episode"

def test_slack_notification(mock_config, episode_info, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "http://slack/webhook")
    mock_config.notification.platform = "slack"
    
    with patch("src.notification.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        
        send_notification(mock_config, episode_info)
        
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]['json']
        assert "New Episode: Test Episode" in payload['text']
