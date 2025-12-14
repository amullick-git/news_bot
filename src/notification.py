
import os
import logging
import requests
import json
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class EpisodeInfo:
    title: str
    mp3_url: str
    links_url: str
    cover_image_url: str
    script_url: str = ""
    duration_str: str = ""
    metrics_summary: str = ""

def send_notification(config, episode: EpisodeInfo):
    """
    Sends a notification to the configured platform (Discord/Slack).
    Requires NOTIFICATION_WEBHOOK_URL environment variable.
    """
    if not config.notification.enabled:
        logger.info("Notifications disabled in config.")
        return

    webhook_url = os.environ.get("NOTIFICATION_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("NOTIFICATION_WEBHOOK_URL not set. Skipping notification.")
        return

    platform = config.notification.platform.lower()
    
    try:
        if "discord" in platform:
            _send_discord(webhook_url, episode)
        elif "slack" in platform:
            _send_slack(webhook_url, episode)
        else:
            logger.warning(f"Unknown notification platform: {platform}")
            
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

def _send_discord(url: str, episode: EpisodeInfo):
    # Discord Webhook Payload
    fields = [
        {
            "name": "Listen Now",
            "value": f"[Download MP3]({episode.mp3_url})",
            "inline": True
        },
        {
            "name": "Sources",
            "value": f"[View Articles]({episode.links_url})",
            "inline": True
        }
    ]

    if episode.script_url:
        fields.append({
            "name": "Script",
            "value": f"[Read Script]({episode.script_url})",
            "inline": True
        })

    if episode.metrics_summary:
        fields.append({
            "name": "Metrics",
            "value": episode.metrics_summary,
            "inline": False
        })

    payload = {
        "username": "News Bot",
        "avatar_url": episode.cover_image_url,
        "embeds": [{
            "title": f"🎙️ New Episode: {episode.title}",
            "description": "Your latest news briefing is ready.",
            "url": episode.links_url,
            "color": 3447003, # Blueish
            "fields": fields,
            "footer": {
                "text": f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            },
            "thumbnail": {
                "url": episode.cover_image_url
            }
        }]
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    logger.info("Discord notification sent successfully.")

def _send_slack(url: str, episode: EpisodeInfo):
    # Slack Webhook Payload (Block Kit)
    
    links_text = f"<{episode.mp3_url}|Listen to MP3> | <{episode.links_url}|View Sources>"
    if episode.script_url:
        links_text += f" | <{episode.script_url}|Read Script>"

    payload = {
        "text": f"New Episode: {episode.title}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎙️ {episode.title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Your new episode is ready!* \n{links_text}"
                },
                "accessory": {
                    "type": "image",
                    "image_url": episode.cover_image_url,
                    "alt_text": "Cover Image"
                }
            }
        ]
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    logger.info("Slack notification sent successfully.")
