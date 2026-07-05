#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -d ".venv" ]; then
    source ".venv/bin/activate"
fi

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

mkdir -p tests/e2e/reports

echo "=========================================="
echo "  DVA Tool - Playwright E2E Test Suite"
echo "=========================================="
echo ""

echo "Running all E2E tests..."
python -m pytest tests/e2e/ \
    --html=tests/e2e/reports/report.html \
    --self-contained-html \
    --junit-xml=tests/e2e/reports/junit.xml \
    --screenshot=only-on-failure \
    --tracing=retain-on-failure \
    --video=retain-on-failure \
    -v \
    "$@"

echo ""
echo "=========================================="
echo "  Reports generated:"
echo "  HTML:   tests/e2e/reports/report.html"
echo "  JUnit:  tests/e2e/reports/junit.xml"
echo "=========================================="
