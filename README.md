# Video Generation

AI-powered talking-head video generator using LivePortrait (head motion) + Wav2Lip (lip sync) + GFPGAN (face restoration).

---

## Prerequisites

### Python
- **Mac:** Python 3.10 — `brew install python@3.10`
- **Windows:** Python 3.10+ from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"** during install

### ffmpeg
Required for all video processing. Must be on your PATH.

- **Mac:** `brew install ffmpeg`
- **Windows:** Download [ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/), extract it, and add the `bin\` folder to your system PATH

Verify with: `ffmpeg -version`

---

## Setup

### Mac

```bash
chmod +x setup_venv.sh
./setup_venv.sh
```

### Windows

Double-click `setup_venv.bat` or run in Command Prompt:

```bat
setup_venv.bat
```

The script will check for Python and ffmpeg, create a virtual environment, and install all dependencies.

---

## Download Models & Repos

After setup, activate the environment and run:

**Mac:**
```bash
source venv/bin/activate
python -c "from liveportrait.setup import setup_all; setup_all()"
```

**Windows:**
```bat
venv\Scripts\activate.bat
python -c "from liveportrait.setup import setup_all; setup_all()"
```

This will:
- Clone LivePortrait and Wav2Lip repos into `liveportrait/`
- Download LivePortrait pretrained weights (~1.5 GB)
- Download Wav2Lip checkpoint (~700 MB)
- Download GFPGANv1.4 weights (~700 MB)
- Download face detection model

---

## Assets

Place your input files in `assets/`:

| File | Description |
|------|-------------|
| `assets/<face>.jpg` | Source face image |
| `assets/<audio>.wav` | Audio file for lip sync |

Driving video PKL templates go in `liveportrait/driving_videos/`. The setup script populates defaults.

---

## Project Structure

```
video-generation/
├── assets/                  # Input files (face images, audio)
├── liveportrait/            # LivePortrait + Wav2Lip pipeline
│   ├── LivePortrait/        # Cloned by setup_all() — not versioned
│   ├── Wav2Lip/             # Cloned by setup_all() — not versioned
│   ├── driving_videos/      # PKL motion templates
│   ├── gfpgan_weights/      # GFPGANv1.4.pth — downloaded by setup_all()
│   ├── config.py
│   ├── setup.py             # setup_all() lives here
│   └── steps.py
├── video_creator/           # Video layout and rendering
├── gfpgan/                  # GFPGAN weights dir
├── requirements.txt
├── setup_venv.sh            # Mac setup
└── setup_venv.bat           # Windows setup
```

---

## Notes

- **H.264 encoding** is auto-detected at runtime: Apple VideoToolbox (Mac) → NVENC (Windows/NVIDIA) → libx264 (software fallback). No configuration needed.
- **MPS (Apple Silicon)** and **CUDA (NVIDIA)** are used automatically when available; both fall back to CPU.
- Large files (model weights, `.mp4` driving videos, cloned repos) are excluded from git — they are downloaded by `setup_all()`.
