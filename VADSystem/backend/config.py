"""Configuration for VAD System"""
import os

# Paths may be overridden by environment variables; dataset contents stay local.
import sys
from pathlib import Path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = str(Path(__file__).resolve().parents[2])
COMFYUI_PATH = os.environ.get("COMFYUI_PATH", os.path.join(REPO_ROOT, "external", "ComfyUI"))
MOTIONSTREAMER_PATH = os.environ.get("MOTIONSTREAMER_PATH", os.path.join(REPO_ROOT, "external", "MotionStreamer"))
PRODISC_VAD_PATH = os.environ.get("PRODISC_VAD_PATH", os.path.join(REPO_ROOT, "external", "ProDisc-VAD"))
WORKFLOW_DIR = os.path.join(REPO_ROOT, "ComfyUI")
COMFYUI_PYTHON = os.environ.get("COMFYUI_PYTHON", sys.executable)
MOTIONSTREAMER_PYTHON = os.environ.get("MOTIONSTREAMER_PYTHON", sys.executable)
PRODISC_PYTHON = os.environ.get("PRODISC_PYTHON", sys.executable)

# ComfyUI settings
COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "127.0.0.1")
COMFYUI_PORT = int(os.environ.get("COMFYUI_PORT", "8188"))
COMFYUI_API_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

# Background images
SHT_BACKGROUND_DIR = os.path.join(COMFYUI_PATH, "sht_background")
UCF_BACKGROUND_DIR = os.path.join(COMFYUI_PATH, "ucf_background")
SYSTEM_BACKGROUND_DIR = os.path.join(COMFYUI_PATH, "system_background")  # System default

# Dataset paths
DATASET_PATH = os.environ.get("DATASET_PATH", os.path.join(PRODISC_VAD_PATH, "dataset"))
SHT_FEATURE_PATH = os.path.join(DATASET_PATH, "shanghaitech", "SH_clip_video_features")
UCF_FEATURE_PATH = os.path.join(DATASET_PATH, "ucf-crime", "UCFClipFeatures")

DEFAULT_SYNTHETIC_RATIOS = {"shanghaitech": 0.5, "ucf-crime": 0.05}

# Model checkpoints
CKPT_PATH = os.environ.get("CKPT_PATH", os.path.join(PRODISC_VAD_PATH, "ckpt"))

# Legacy checkpoint locations. Sampling settings and metrics come from run records.
MODELS = {
    # ShanghaiTech models
    "sht_baseline": {
        "name": "SHT_Baseline",
        "dataset": "shanghaitech",
        "path": os.path.join(CKPT_PATH, "SHT_Baseline", "seed1", "best_model.pkl"),
        "log_path": os.path.join(PRODISC_VAD_PATH, "logs", "SHT_Baseline.log"),
        "default": False,
    },
    "sht_best": {
        "name": "SHT_Best",
        "dataset": "shanghaitech",
        "path": os.path.join(CKPT_PATH, "SHT_Best", "seed1", "best_model.pkl"),
        "log_path": os.path.join(PRODISC_VAD_PATH, "logs", "SHT_Best.log"),
        "default": True,
    },
    # UCF-Crime models
    "ucf_baseline": {
        "name": "UCF_Baseline",
        "dataset": "ucf-crime",
        "path": os.path.join(CKPT_PATH, "UCF_Baseline", "seed1", "best_model.pkl"),
        "log_path": os.path.join(PRODISC_VAD_PATH, "logs", "UCF_Baseline.log"),
        "default": False,
    },
    "ucf_best": {
        "name": "UCF_Best",
        "dataset": "ucf-crime",
        "path": os.path.join(CKPT_PATH, "UCF_Best", "seed1", "best_model.pkl"),
        "log_path": os.path.join(PRODISC_VAD_PATH, "logs", "UCF_Best.log"),
        "default": True,
    },
}

# MotionStreamer settings
MOTION_SERVER_URL = os.environ.get("MOTION_SERVER_URL", "http://127.0.0.1:5100")  # Persistent motion generation server
MOTION_OUTPUT_DIR = os.path.join(MOTIONSTREAMER_PATH, "runs_vad_system")
SHT_MOTION_DIR = os.path.join(MOTIONSTREAMER_PATH, "runs_sht_abnormal")
UCF_MOTION_DIR = os.path.join(MOTIONSTREAMER_PATH, "runs_ucf_abnormal")

# Upload and output directories
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))

# Video generation output directory (in ComfyUI)
VIDEO_OUTPUT_DIR = os.path.join(COMFYUI_PATH, "output", "video")
VIDEO_SYSTEM_FOLDER = "system_generated"  # Default system output folder

# Synthetic video directories (for file management)
SHT_SYNTHETIC_VIDEO_DIR = os.path.join(COMFYUI_PATH, "output", "video")
UCF_SYNTHETIC_VIDEO_DIR = os.path.join(COMFYUI_PATH, "output", "video")

# Feature extraction default output folders
SHT_FEATURE_SYSTEM_DIR = os.path.join(DATASET_PATH, "shanghaitech", "SH_clip_video_features", "system_extracted")
UCF_FEATURE_SYSTEM_DIR = os.path.join(DATASET_PATH, "ucf-crime", "UCFClipFeatures", "system_extracted")

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MOTION_OUTPUT_DIR, exist_ok=True)
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(VIDEO_OUTPUT_DIR, VIDEO_SYSTEM_FOLDER), exist_ok=True)
os.makedirs(SHT_FEATURE_SYSTEM_DIR, exist_ok=True)
os.makedirs(UCF_FEATURE_SYSTEM_DIR, exist_ok=True)
os.makedirs(SYSTEM_BACKGROUND_DIR, exist_ok=True)
