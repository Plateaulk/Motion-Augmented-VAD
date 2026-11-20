"""Batch motion export adapted from MotionStreamer's demo_t2m.py.

Save normalized motion, denormalized motion and renderer inputs. Repeats
extend the denormalized sequence and its joint and pelvis trajectories.
"""
import argparse
import os
import random
import sys
import warnings

import numpy as np
import torch

warnings.filterwarnings("ignore")

import options.option_transformer as option_trans
import models.tae as tae
from models.llama_model import LLaMAHF, LLaMAHFConfig

from sentence_transformers import SentenceTransformer
from visualization.recover_visualize import recover_from_local_position


def parse_wrapper(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--out_root", type=str, default="runs_test")
    p.add_argument("--sample_id", type=str, default="000001")
    p.add_argument("--t5_path", type=str, default="sentencet5-xxl")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--repeat_drop_first", action="store_true")
    p.add_argument("--stop_threshold", type=float, default=None)
    p.add_argument("--block_size", type=int, default=None)
    extra, rest = p.parse_known_args(argv)
    return extra, rest


def main():
    extra, rest = parse_wrapper(sys.argv[1:])

    # ---- parse repo args safely ----
    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0]] + rest
        args = option_trans.get_args_parser()  # returns Namespace in this repo
    finally:
        sys.argv = old_argv

    # ---- output dir ----
    out_dir = os.path.join(extra.out_root, str(extra.sample_id))
    os.makedirs(out_dir, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    random.seed(1)
    np.random.seed(1)
    torch.manual_seed(1)

    stop_threshold = float(extra.stop_threshold) if extra.stop_threshold is not None else 0.1
    block_size = int(extra.block_size) if extra.block_size is not None else 78
    repeat = int(extra.repeat)
    drop_first = bool(extra.repeat_drop_first)

    print("[Info] device=%s" % device)
    print("[Info] out_dir=%s" % out_dir)
    print("[Info] stop_threshold=%.4f block_size=%d repeat=%d drop_first=%s" % (stop_threshold, block_size, repeat, drop_first))

    # ---- Text encoder ----
    t5_model = SentenceTransformer(extra.t5_path)
    t5_model.eval()
    for p in t5_model.parameters():
        p.requires_grad = False

    # ---- Networks ----
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

    config = LLaMAHFConfig.from_name("Normal_size")
    config.block_size = block_size
    trans_encoder = LLaMAHF(config, args.num_diffusion_head_layers, args.latent_dim, device)

    print("[Demo] loading checkpoint from %s" % args.resume_pth)
    ckpt = torch.load(args.resume_pth, map_location="cpu")
    net.load_state_dict(ckpt["net"], strict=True)
    net.eval().to(device)

    if getattr(args, "resume_trans", None) is not None:
        print("[Demo] loading transformer checkpoint from %s" % args.resume_trans)
        ckpt = torch.load(args.resume_trans, map_location="cpu")
        new_ckpt_trans = {}
        for key in ckpt["trans"].keys():
            if key.split(".")[0] == "module":
                new_key = ".".join(key.split(".")[1:])
            else:
                new_key = key
            new_ckpt_trans[new_key] = ckpt["trans"][key]
        trans_encoder.load_state_dict(new_ckpt_trans, strict=True)
    trans_encoder.eval().to(device)

    reference_end_latent = torch.from_numpy(np.load("reference_end_latent_t2m_272.npy")).to(device)
    mean = np.load("humanml3d_272/mean_std/Mean.npy")
    std = np.load("humanml3d_272/mean_std/Std.npy")

    # ---- forward inference ----
    motion_latents = trans_encoder.sample_for_eval_CFG_inference(
        text=args.text,
        tokenizer=t5_model,
        device=device,
        reference_end_latent=reference_end_latent,
        threshold=stop_threshold,
    )

    # ---- forward decode ----
    motion_seqs = net.forward_decoder(motion_latents)
    motion_norm = motion_seqs.squeeze(0).detach().cpu().numpy().astype(np.float32)  # (T,272)
    one_denorm = (motion_norm * std + mean).astype(np.float32)

    np.save(os.path.join(out_dir, "motion_272_norm.npy"), motion_norm)

    # ---- repeat denorm ----
    motion_denorm = one_denorm
    if repeat > 1:
        chunks = []
        for k in range(repeat):
            m = one_denorm.copy()
            if k > 0 and drop_first:
                m = m[1:]
            chunks.append(m)
        motion_denorm = np.concatenate(chunks, axis=0).astype(np.float32)
        print("[Demo] repeated motion: repeat=%d -> frames=%d" % (repeat, motion_denorm.shape[0]))
    np.save(os.path.join(out_dir, "motion_272_denorm.npy"), motion_denorm)

    # ---- recover & stitch joints xyz for renderer ----
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
        print("[Demo] pelvis disp(xz)=%.4f  frames=%d" % (disp, pelvis_traj.shape[0]))
    except Exception as e:
        print("[WARN] failed to recover/save joints_xyz/pelvis_traj: %r" % (e,))

    print("[Demo] saved sample to: %s" % out_dir)
    print("       - motion_272_denorm.npy")
    print("       - joints_xyz.npy")


if __name__ == "__main__":
    main()
