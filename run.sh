#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Ensure config.yaml exists
if [ ! -f config.yaml ]; then
    echo "config.yaml not found - copying from config.example.yaml"
    cp config.example.yaml config.yaml
fi

# Ensure data directory exists
mkdir -p data

echo "Rebuilding and starting SHIAB..."
docker compose up --build -d

echo ""
echo "SHIAB is running at http://localhost:8000"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f    - follow logs"
echo "  docker compose down       - stop"
echo "  docker compose restart    - restart without rebuild"
