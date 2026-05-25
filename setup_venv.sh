#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "Creating Python 3.10 venv..."
python3.10 -m venv venv

echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete."
echo "To activate: source api_v4/venv/bin/activate"
echo "To start the service: uvicorn main:app --host 0.0.0.0 --port 8003"
echo ""
echo "NOTE: Place a neutral driving video at:"
echo "  api_v4/liveportrait/driving_videos/neutral.mp4"
echo "  This is used as the default head motion reference for all generations."
echo "  Any short (~5-10s) clip of a person talking neutrally works well."
echo ""
echo "NOTE: Set LIPSYNC_API_URL env var if api_v2 runs on a non-default port/host."
echo "  Default: http://localhost:8001"
