#!/bin/bash
set -e

# Stage the episodes directory (MP3s, Markdown sources, HTML links)
git add docs/episodes/

# Stage the index.html file (updated with new links)
if [ -f docs/index.html ]; then
    git add docs/index.html
fi

# Stage the metrics logs (if they exist)
for file in metrics/metrics_prod.md metrics/metrics_test.md metrics/metrics_stats.json; do
    if [ -f "$file" ]; then
        git add "$file"
    fi
done

# Stage archive data
if ls data/archive/*.json 1> /dev/null 2>&1; then
    git add -f data/archive/*.json
fi

# Debug: Show status before we exit
echo "Staging complete. Git status:"
git status --porcelain
