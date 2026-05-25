#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# ── Homebrew ────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found — installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for the rest of this session (Apple Silicon path)
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# ── Python 3.10 ─────────────────────────────────────────────────────────────
if ! command -v python3.10 &>/dev/null; then
    echo "Python 3.10 not found — installing via Homebrew..."
    brew install python@3.10
fi

# ── ffmpeg ───────────────────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "ffmpeg not found — installing via Homebrew..."
    brew install ffmpeg
fi

# ── Virtual environment ──────────────────────────────────────────────────────
echo "Creating Python 3.10 venv..."
python3.10 -m venv venv

echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete."
echo ""
echo "To activate the environment in future sessions:"
echo "  source venv/bin/activate"
echo ""
echo "Next step — download models and clone repos:"
echo "  python -c \"from liveportrait.setup import setup_all; setup_all()\""
echo ""
echo "NOTE: Place a driving video PKL at:"
echo "  liveportrait/driving_videos/"
echo "  (run setup_all above to populate defaults)"
