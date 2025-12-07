#!/bin/bash
# Pre-push hook to run tests and verification

echo "🚀 Running pre-push checks..."

# 1. Run Unit Tests & E2E Tests
echo "🧪 Running pytest..."
python3 -m pytest tests/
if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Push aborted."
    exit 1
fi

# 2. Run Staging Verification (Safe Guard)
echo "🛡️  Running staging verification..."
python3 tests/verify_staging.py
if [ $? -ne 0 ]; then
    echo "❌ Staging verification failed. Push aborted."
    exit 1
fi

echo "✅ All checks passed. Pushing..."
exit 0
