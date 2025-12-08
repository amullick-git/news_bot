"""
Configuration Management
========================

This module handles loading and parsing the application configuration.
It uses `dataclasses` to define the expected structure of the configuration
and `PyYAML` to read from the `config.yaml` file.
"""
import yaml
import os
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ProcessingConfig:
    duration_minutes: int
    words_per_min: int
    max_per_feed: int
    max_final_articles: int
    retention_days: int
    gemini_model: str = "gemini-2.5-flash"
    gemini_filter_model: str = "gemini-2.5-flash-lite"
    local_model: str = "all-MiniLM-L6-v2"
    fetch_limit: int = 100
    local_prefilter_limit: int = 50
    voice_type: str = "wavenet"
    max_parallel_tts_calls: int = 5

@dataclass
class PodcastConfig:
    base_url: str
    title: str
    author: str
    image_filename: str
    language: str
    episodes_dir: str
    
    @property
    def image_url(self) -> str:
        return f"{self.base_url}/{self.image_filename}"

@dataclass
class Config:
    feeds: Dict[str, List[str]]
    keywords: Dict[str, List[str]]
    processing: ProcessingConfig
    podcast: PodcastConfig
    processing_overrides: Dict[str, ProcessingConfig] = None

def load_config(config_path: str = "config.yaml") -> Config:
    if not os.path.exists(config_path):
        # Fallback to looking in parent dir if running from src
        parent_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_path)
        if os.path.exists(parent_path):
            config_path = parent_path
        else:
            raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    overrides = {}
    if "processing_overrides" in raw:
        base_processing = raw["processing"]
        for key, val in raw["processing_overrides"].items():
            # Merge base config with override values
            merged = base_processing.copy()
            if val:
                merged.update(val)
            overrides[key] = ProcessingConfig(**merged)

    return Config(
        feeds=raw["feeds"],
        keywords=raw["keywords"],
        processing=ProcessingConfig(**raw["processing"]),
        podcast=PodcastConfig(**raw["podcast"]),
        processing_overrides=overrides
    )
