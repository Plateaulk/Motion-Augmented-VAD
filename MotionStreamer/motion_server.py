# -*- coding: utf-8 -*-
"""
motion_server.py — Persistent Motion Generation Server

Loads all models once on startup, then accepts HTTP requests for motion generation.
This avoids the 19GB+ SentenceT5-XXL model reload on every request.

Usage:
    python motion_server.py [--port 5100] [--t5_path sentencet5-xxl]

API:
    POST /generate  { "text": "...", "out_root": "...", "sample_id": "...", ... }
    GET  /health    -> { "status": "ready" }
"""
import os
import sys
import json
import time
import argparse
import warnings
import random
import traceback
warnings.filterwarnings("ignore")

import numpy as np
import torch
from flask import Flask, request, jsonify

# Ensure MotionStreamer root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import options.option_transformer as option_trans
import models.tae as tae
from models.llama_model import LLaMAHF, LLaMAHFConfig
from sentence_transformers import SentenceTransformer
from visualization.recover_visualize import recover_from_local_position

app = Flask(__name__)

# ── Global model state ──────────────────────────────────
_models = {}
_ready = False


def load_models(t5_path="sentencet5-xxl", block_size=78):
    """Load all models once into GPU memory."""
    global _models, _ready
    t0 = time.time()

    # Parse default args from the repo's option parser
    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0],
                     "--resume-pth", "Causal_TAE/net_last.pth",
                     "--resume-trans", "Experiments/t2m_model/latest.pth",
                     "--text", "dummy"]
        args = option_trans.get_args_parser()
    finally:
        sys.argv = old_argv

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[MotionServer] device = {device}")

    # ── Text encoder (19 GB on disk — keep on CPU to save GPU VRAM) ──
    print(f"[MotionServer] Loading SentenceT5 from {t5_path} (CPU) ...")
    t5_model = SentenceTransformer(t5_path, device="cpu")
    t5_model.eval()
    for p in t5_model.parameters():
        p.requires_grad = False
    print(f"[MotionServer] SentenceT5 loaded on CPU ({time.time()-t0:.1f}s)")

    # ── TAE ─────────────────────────────────────────────
    clip_range = [-30, 20]
    net = tae.Causal_HumanTAE(
        hidden_size=args.hidden_size,
        down_t=args.down_t,
        stride_t=args.stride_t,
        depth=args.depth,
        dilation_growth_rate=args.dilation_growth_rate,
        activation="relu",
        latent_dim=args.latent_dim,
        clip_range=clip_range,
    )
    print(f"[MotionServer] Loading TAE checkpoint: {args.resume_pth}")
    ckpt = torch.load(args.resume_pth, map_location="cpu")
    net.load_state_dict(ckpt["net"], strict=True)
    net.eval().to(device)

    # ── Transformer ─────────────────────────────────────
    config = LLaMAHFConfig.from_name("Normal_size")
    config.block_size = block_size
    trans_encoder = LLaMAHF(config, args.num_diffusion_head_layers, args.latent_dim, device)
    print(f"[MotionServer] Loading Transformer checkpoint: {args.resume_trans}")
    ckpt_t = torch.load(args.resume_trans, map_location="cpu")
    new_ckpt_trans = {}
    for key in ckpt_t["trans"].keys():
        new_key = ".".join(key.split(".")[1:]) if key.split(".")[0] == "module" else key
        new_ckpt_trans[new_key] = ckpt_t["trans"][key]
    trans_encoder.load_state_dict(new_ckpt_trans, strict=True)
    trans_encoder.eval().to(device)

    # ── Reference data ──────────────────────────────────
    reference_end_latent = torch.from_numpy(
        np.load("reference_end_latent_t2m_272.npy")
    ).to(device)
    mean = np.load("humanml3d_272/mean_std/Mean.npy")
    std  = np.load("humanml3d_272/mean_std/Std.npy")

    _models = {
        "device": device,
        "t5_model": t5_model,
        "net": net,
        "trans_encoder": trans_encoder,
        "reference_end_latent": reference_end_latent,
        "mean": mean,
        "std": std,
        "args": args,
    }
    _ready = True
    elapsed = time.time() - t0
    print(f"[MotionServer] ✅ All models loaded in {elapsed:.1f}s  —  ready for requests")


# ── Inference function (no model loading) ───────────────
def generate_motion(text, out_root, sample_id,
                    stop_threshold=0.1, repeat=1, drop_first=False):
    """Run motion generation using pre-loaded models."""
    random.seed(1)
    np.random.seed(1)
    torch.manual_seed(1)
    m = _models
    device = m["device"]
    t5_model = m["t5_model"]
    net = m["net"]
    trans_encoder = m["trans_encoder"]
    reference_end_latent = m["reference_end_latent"]
    mean = m["mean"]
    std = m["std"]

    out_dir = os.path.join(out_root, str(sample_id))
    os.makedirs(out_dir, exist_ok=True)

    print(f"[MotionServer] Generating: text='{text}' → {out_dir}")
    t0 = time.time()

    # Forward inference
    with torch.no_grad():
        t_enc = time.time()
        motion_latents = trans_encoder.sample_for_eval_CFG_inference(
            text=text,
            tokenizer=t5_model,
            device=device,
            reference_end_latent=reference_end_latent,
            threshold=stop_threshold,
        )
        t_dec = time.time()
        print(f"[MotionServer] ⏱ Transformer inference: {t_dec - t_enc:.2f}s")
        # Decode
        motion_seqs = net.forward_decoder(motion_latents)
        print(f"[MotionServer] ⏱ Decoder: {time.time() - t_dec:.2f}s")

    motion_norm = motion_seqs.squeeze(0).detach().cpu().numpy().astype(np.float32)
    one_denorm = (motion_norm * std + mean).astype(np.float32)
    np.save(os.path.join(out_dir, "motion_272_norm.npy"), motion_norm)

    # Repeat
    motion_denorm = one_denorm
    if repeat > 1:
        chunks = []
        for k in range(repeat):
            m_ = one_denorm.copy()
            if k > 0 and drop_first:
                m_ = m_[1:]
            chunks.append(m_)
        motion_denorm = np.concatenate(chunks, axis=0).astype(np.float32)
        print(f"[MotionServer] repeated motion: repeat={repeat} -> frames={motion_denorm.shape[0]}")
    np.save(os.path.join(out_dir, "motion_272_denorm.npy"), motion_denorm)

    # Recover joints xyz
    try:
        one_xyz = recover_from_local_position(one_denorm, 22).reshape(-1, 22, 3).astype(np.float32)
        if repeat > 1:
            delta = (one_xyz[-1, 0, :] - one_xyz[0, 0, :]).astype(np.float32)
            xyz_chunks = []
            for k in range(repeat):
                ck = one_xyz + (k * delta[None, None, :])
                if k > 0 and drop_first:
                    ck = ck[1:]
                xyz_chunks.append(ck)
            joints_xyz = np.concatenate(xyz_chunks, axis=0).astype(np.float32)
        else:
            joints_xyz = one_xyz

        pelvis_traj = joints_xyz[:, 0, :].astype(np.float32)
        np.save(os.path.join(out_dir, "joints_xyz.npy"), joints_xyz)
        np.save(os.path.join(out_dir, "pelvis_traj.npy"), pelvis_traj)

        disp = float(np.linalg.norm(pelvis_traj[-1, [0, 2]] - pelvis_traj[0, [0, 2]]))
        print(f"[MotionServer] pelvis disp(xz)={disp:.4f}  frames={pelvis_traj.shape[0]}")
    except Exception as e:
        print(f"[MotionServer][WARN] failed to recover joints_xyz: {e}")

    elapsed = time.time() - t0
    print(f"[MotionServer] ✅ Generated in {elapsed:.1f}s → {out_dir}")

    return {
        "success": True,
        "out_dir": out_dir,
        "frames": int(motion_denorm.shape[0]),
        "elapsed": round(elapsed, 2),
    }


# ── Flask Routes ────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ready" if _ready else "loading"})


@app.route("/generate", methods=["POST"])
def handle_generate():
    if not _ready:
        return jsonify({"error": "Models are still loading, please wait"}), 503

    data = request.json or {}
    text = data.get("text", "")
    out_root = data.get("out_root", "runs_test")
    sample_id = data.get("sample_id", "000001")
    stop_threshold = float(data.get("stop_threshold", 0.1))
    repeat = int(data.get("repeat", 1))
    drop_first = bool(data.get("drop_first", False))

    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = generate_motion(
            text=text,
            out_root=out_root,
            sample_id=sample_id,
            stop_threshold=stop_threshold,
            repeat=repeat,
            drop_first=drop_first,
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--t5_path", type=str, default="sentencet5-xxl")
    parser.add_argument("--block_size", type=int, default=78)
    cli_args = parser.parse_args()

    # Change to MotionStreamer directory so relative paths work
    os.chdir(SCRIPT_DIR)

    # Load models first
    load_models(t5_path=cli_args.t5_path, block_size=cli_args.block_size)

    # Start Flask server
    app.run(host="127.0.0.1", port=cli_args.port, threaded=False)
