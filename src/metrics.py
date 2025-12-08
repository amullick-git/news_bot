import os
from datetime import datetime
import json
from typing import List, Dict, Any
from urllib.parse import urlparse
from .utils import get_logger

logger = get_logger(__name__)

class MetricsLogger:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        # Create metrics directory under base_dir
        self.metrics_dir = os.path.join(base_dir, "metrics")
        os.makedirs(self.metrics_dir, exist_ok=True)
        
        self.stats_file = os.path.join(self.metrics_dir, "metrics_stats.json")

    def _load_stats(self) -> Dict[str, Any]:
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load stats: {e}")
        return {"tts_usage": {}}

    def _save_stats(self, stats: Dict[str, Any]):
        try:
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")

    def _update_tts_stats(self, model: str, chars: int) -> Dict[str, int]:
        stats = self._load_stats()
        usage = stats.setdefault("tts_usage", {})
        usage[model] = usage.get(model, 0) + chars
        self._save_stats(stats)
        return usage

    def _get_source_name(self, item: Dict[str, Any]) -> str:
        """Helper to get friendly source name or domain"""
        if item.get("source_name"):
            return item["source_name"]
        
        # Fallback to domain
        link = item.get("link", "")
        try:
            return urlparse(link).netloc.replace("www.", "")
        except:
            return "unknown"

    def _count_by_source(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {}
        for item in items:
            src = self._get_source_name(item)
            counts[src] = counts.get(src, 0) + 1
        return counts

    def log_run(self, 
                fetched_items: List[Dict[str, Any]], 
                shortlisted_items: List[Dict[str, Any]], 
                run_type: str, 
                is_test: bool = False,
                links_file: str = None,
                local_ai_items: List[Dict[str, Any]] = None,
                tts_stats: Dict[str, Any] = None):
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Calculate stats
        fetched_counts = self._count_by_source(fetched_items)
        shortlisted_counts = self._count_by_source(shortlisted_items)
        local_ai_counts = self._count_by_source(local_ai_items) if local_ai_items else {}
        
        # Merge all known sources
        all_sources = sorted(list(set(fetched_counts.keys()) | set(shortlisted_counts.keys()) | set(local_ai_counts.keys())))
        
        # Build Markdown Report
        lines = []
        lines.append(f"## Run: {timestamp} (Type: {run_type})")
        
        if links_file:
            # Assumes relative path from where the log is viewed or absolute?
            # Usually we are at root. links are in `episodes/`.
            # Let's just print the filename for now or relative path.
            lines.append(f"**Links File**: [{links_file}](episodes/{links_file})\n")
            
        stats_line = f"**Total Fetched**: {len(fetched_items)}"
        if local_ai_items is not None:
             stats_line += f" -> **Stage 1 (Local AI)**: {len(local_ai_items)}"
             stats_line += f" -> **Stage 2 (Gemini Final)**: {len(shortlisted_items)}\n"
        else:
             stats_line += f" -> **Final Selection**: {len(shortlisted_items)}\n"
        
        lines.append(stats_line)

        if tts_stats:
            model = tts_stats.get("model", "unknown")
            chars = tts_stats.get("chars", 0)
            
            # Update and get running totals
            if not is_test:  # Only update running totals for prod runs
                running_totals = self._update_tts_stats(model, chars)
                total_for_model = running_totals.get(model, 0)
            else:
                total_for_model = chars # Just show current for test

            lines.append(f"**TTS Usage**: {chars} chars (Model: {model}) -> **Running Total**: {total_for_model} chars\n")
        
        lines.append("### Breakdown by Source")
        lines.append("| Source | Fetched | Stage 1 (Local AI) | Selected |")
        lines.append("|---|---|---|---|")
        
        for src in all_sources:
            f_count = fetched_counts.get(src, 0)
            s1_count = local_ai_counts.get(src, 0)
            s2_count = shortlisted_counts.get(src, 0)
            lines.append(f"| {src} | {f_count} | {s1_count} | {s2_count} |")
            
        lines.append("\n" + "-"*40 + "\n")
        
        report_content = "\n".join(lines)
        
        # Determine filename
        filename = "metrics_test.md" if is_test else "metrics_prod.md"
        filepath = os.path.join(self.metrics_dir, filename)
        
        self._prepend_to_file(filepath, report_content)

    def _prepend_to_file(self, filepath: str, new_content: str):
        """Prepends content to a file efficiently"""
        existing_content = ""
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    existing_content = f.read()
            except Exception as e:
                logger.error(f"Failed to read existing metrics: {e}")
                
        with open(filepath, "w") as f:
            f.write(new_content + "\n" + existing_content)
            
        logger.info(f"Metrics logged to {filepath}")
