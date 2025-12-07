#!/bin/bash
set -e

# Stage the episodes directory (MP3s, Markdown sources, HTML links)
git add episodes/

# Stage the index.html file (updated with new links)
git add index.html

# Stage the metrics logs (if they exist)
git add metrics_prod.md || true
git add metrics_test.md || true

# Note: feed.xml is handled separately in the workflow after regeneration
