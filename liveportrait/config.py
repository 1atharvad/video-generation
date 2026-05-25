from pathlib import Path

LIVEPORTRAIT_DIR = Path(__file__).resolve().parent
BASE_DIR = LIVEPORTRAIT_DIR.parent.parent
AUDIO_DIR = Path(BASE_DIR, "n8n_files", "audio_files")

# LivePortrait
LP_REPO_DIR = Path(LIVEPORTRAIT_DIR, "LivePortrait")
LP_REPO_URL = "https://github.com/KlingAIResearch/LivePortrait.git"
LP_INFERENCE_SCRIPT = Path(LP_REPO_DIR, "inference.py")
DRIVING_VIDEOS_DIR = Path(LIVEPORTRAIT_DIR, "driving_videos")

# Wav2Lip
WAV2LIP_DIR = Path(LIVEPORTRAIT_DIR, "Wav2Lip")
WAV2LIP_REPO_URL = "https://github.com/Rudrabha/Wav2Lip.git"
WAV2LIP_INFERENCE_SCRIPT = Path(WAV2LIP_DIR, "inference.py")
CHECKPOINTS_DIR = Path(WAV2LIP_DIR, "checkpoints")
FACE_DET_DIR = Path(WAV2LIP_DIR, "face_detection", "detection", "sfd")
CHECKPOINT_PATH = Path(CHECKPOINTS_DIR, "wav2lip_gan.pth")
FACE_DET_URL = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
CHECKPOINT_HF_REPO = "numz/wav2lip_studio"
CHECKPOINT_HF_FILE = "Wav2lip/wav2lip_gan.pth"

# GFPGAN (face restoration)
GFPGAN_WEIGHTS_DIR = Path(LIVEPORTRAIT_DIR, "gfpgan_weights")
GFPGAN_MODEL_PATH = Path(GFPGAN_WEIGHTS_DIR, "GFPGANv1.4.pth")
GFPGAN_MODEL_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth"
