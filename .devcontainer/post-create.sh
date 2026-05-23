#!/bin/bash
# post-create.sh — Post-container initialization script

set -e

echo "=== Upgrading Package Manager ==="
pip install --upgrade pip

echo "=== Installing Python Requirements ==="
pip install -r requirements.txt

echo "=== Installing Playwright Browser Binaries ==="
playwright install chromium

echo "=== DevContainer Setup Successfully Completed ==="
