#!/bin/bash
set -e

# Stage the episodes directory (MP3s, Markdown sources, HTML links)
git add docs/episodes/

# Stage the index.html file (updated with new links)
git add docs/index.html

# Stage the metrics logs (if they exist)
git add metrics/metrics_prod.md || true
git add metrics/metrics_test.md || true
git add metrics/metrics_stats.json || true
git add data/archive/*.json || true

# Note: feed.xml is handled separately in the workflow after regeneration
