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

# Stage archive data (both new and deleted)
# 1. Add new/modified files (force needed due to gitignore)
if ls data/archive/*.json 1> /dev/null 2>&1; then
    git add -f data/archive/*.json
fi
# 2. Stage deletions (git add -u handles modified/deleted affecting the index)
# We target the directory specifically.
git add -u data/archive/

# Ensure episode deletions are also caught (unlikely to be ignored, but safe)
git add -u docs/episodes/

# Debug: Show status before we exit
echo "Staging complete. Git status:"
git status --porcelain
