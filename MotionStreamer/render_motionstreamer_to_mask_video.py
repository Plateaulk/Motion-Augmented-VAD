#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render MotionStreamer motions to:
  - binary mask PNGs
  - composite RGB PNGs (mask pasted onto a background image)
  - mp4 videos (mask.mp4 and composite.mp4) when ffmpeg supports a usable encoder

Batch-friendly conventions:
- If --motion_npy is omitted, provide --out_root + --sample_id and it will read:
    <out_root>/<sample_id>/motion_272_denorm.npy
- If --out_dir is omitted, it will write to:
    <out_root>/<sample_id>/render_yaw<deg>/   (when sample_id used)
  else:
    render_out/<motion_stem>_yaw<deg>/

Python 3.8 compatible (no PEP604 "A | None" annotations).
"""

import os
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np

FLIP_TRAJ_LR = True  # set in main()
import torch
import trimesh
import pyrender
from smplx import SMPL
from tqdm import tqdm


# -------------------------
# Math utils
# -------------------------
def rot_yaw_matrix(yaw_rad: float) -> np.ndarray:
    """World Y-axis rotation (right-handed). Positive yaw turns left."""
    c, s = np.cos(yaw_rad), np.sin(yaw_rad)
    return np.array([[ c, 0.0,  s],
                     [0.0, 1.0, 0.0],
                     [-s, 0.0,  c]], dtype=np.float32)

def apply_yaw(points: np.ndarray, yaw_rad: float) -> np.ndarray:
    """Rotate last-dim=3 points around Y axis."""
    if abs(yaw_rad) < 1e-8:
        return points
    R = rot_yaw_matrix(yaw_rad)
    shp = points.shape
    pts = points.reshape(-1, 3).astype(np.float32)
    pts = pts @ R.T
    return pts.reshape(*shp)

def rot6d_to_rotmat(x6: torch.Tensor) -> torch.Tensor:
    """6D rotation -> 3x3 rotation matrix."""
    a1 = x6[..., 0:3]
    a2 = x6[..., 3:6]
    b1 = torch.nn.functional.normalize(a1, dim=-1)
    b2 = a2 - (b1 * a2).sum(dim=-1, keepdim=True) * b1
    b2 = torch.nn.functional.normalize(b2, dim=-1)
    b3 = torch.cross(b1, b2, dim=-1)
    return torch.stack([b1, b2, b3], dim=-2)

def rotmat_to_rot6d(R: np.ndarray) -> np.ndarray:
    """Rotation matrix (...,3,3) -> 6D (first 2 columns)."""
    return R[..., :, 0:2].reshape(*R.shape[:-2], 6).astype(np.float32)

def look_at(eye, target, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """Camera pose matrix for pyrender."""
    eye = np.array(eye, dtype=np.float32)
    target = np.array(target, dtype=np.float32)
    up = np.array(up, dtype=np.float32)

    forward = target - eye
    forward = forward / (np.linalg.norm(forward) + 1e-8)
    right = np.cross(forward, up)
    right = right / (np.linalg.norm(right) + 1e-8)
    true_up = np.cross(right, forward)

    pose = np.eye(4, dtype=np.float32)
    pose[0:3, 0] = right
    pose[0:3, 1] = true_up
    pose[0:3, 2] = -forward
    pose[0:3, 3] = eye
    return pose

def apply_yaw_to_points(points: np.ndarray, yaw_rad: float) -> np.ndarray:
    """Rotate (T,3) points around Y axis by yaw_rad."""
    if abs(float(yaw_rad)) < 1e-8:
        return points
    c = float(np.cos(yaw_rad))
    s = float(np.sin(yaw_rad))
    R = np.array([[c, 0.0, -s],
                  [0.0, 1.0, 0.0],
                  [s, 0.0,  c]], dtype=np.float32)
    return points @ R.T

def load_pelvis_traj(sample_dir: Path, T: int) -> Optional[np.ndarray]:
    """Load pelvis trajectory (T,3). Prefer pelvis_traj.npy; fallback joints_xyz.npy[:,0]."""
    traj = None
    traj_path = sample_dir / "pelvis_traj.npy"
    joints_path = sample_dir / "joints_xyz.npy"
    if traj_path.exists():
        traj = np.load(str(traj_path)).astype(np.float32)
    elif joints_path.exists():
        j = np.load(str(joints_path)).astype(np.float32)
        if j.ndim == 3 and j.shape[1] >= 1 and j.shape[2] == 3:
            traj = j[:, 0, :]
    if traj is None or traj.ndim != 2 or traj.shape[1] != 3:
        return None
    if traj.shape[0] != T:
        x = np.linspace(0.0, 1.0, traj.shape[0], dtype=np.float32)
        xi = np.linspace(0.0, 1.0, T, dtype=np.float32)
        out = np.zeros((T, 3), dtype=np.float32)
        for k in range(3):
            out[:, k] = np.interp(xi, x, traj[:, k]).astype(np.float32)
        traj = out
    return traj

def load_background_crop(path: str, width: int, height: int) -> np.ndarray:
    """Read background and center-crop to (height,width) after cover-resize (no tiling)."""
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"Failed to read background image: {path}")
    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        raise RuntimeError(f"Invalid background image: {path}")
    scale = max(float(width) / float(w), float(height) / float(h))
    nw, nh = int(round(w * scale)), int(round(h * scale))
    img_rs = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
    y0 = max(0, (nh - height) // 2)
    x0 = max(0, (nw - width) // 2)
    crop = img_rs[y0:y0 + height, x0:x0 + width].copy()
    if crop.shape[0] != height or crop.shape[1] != width:
        crop = cv2.resize(crop, (width, height), interpolation=cv2.INTER_LINEAR)
    return crop




# -------------------------
# Motion parsing
# -------------------------
def detect_motion_format(arr: np.ndarray) -> str:
    if arr.ndim == 3 and arr.shape[-1] == 3:
        return "joints"
    if arr.ndim == 2 and arr.shape[1] == 272:
        return "rep272"
    raise ValueError(f"Unsupported motion shape: {arr.shape}. Expected joints (T,J,3) or rep272 (T,272).")

def rep272_extract(arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    272 layout:
      - first 8 dims: meta
      - joint positions: [8 : 8+3*22]
      - joint velocities: [8+3*22 : 8+6*22]
      - joint rotations 6D: [8+6*22 : 8+12*22]
    """
    T = arr.shape[0]
    joints_pos = arr[:, 8:8+3*22].reshape(T, 22, 3).astype(np.float32)
    joints_vel = arr[:, 8+3*22:8+6*22].reshape(T, 22, 3).astype(np.float32)
    joints_rot6d = arr[:, 8+6*22:8+12*22].reshape(T, 22, 6).astype(np.float32)
    return joints_pos, joints_vel, joints_rot6d


# -------------------------
# Path conventions
# -------------------------
def resolve_sample_motion(out_root: str, sample_id: str) -> Path:
    return Path(out_root) / str(sample_id) / "motion_272_denorm.npy"

def default_out_dir(motion_path: Path, yaw_deg: float) -> Path:
    stem = motion_path.stem
    yaw_str = f"{yaw_deg:.1f}".replace(".", "p").replace("-", "m")
    return Path("render_out") / f"{stem}_yaw{yaw_str}"

def resolve_smpl_path(smpl_arg: str) -> str:
    """
    Priority:
      1) --smpl_path if provided
      2) ./smpl_models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl (repo-local default)
      3) env var SMPL_PATH
      4) auto-search common locations
    """
    if smpl_arg:
        p = Path(smpl_arg).expanduser()
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"--smpl_path not found: {p}")

    repo_default = Path.cwd() / "smpl_models" / "basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl"
    if repo_default.exists():
        return str(repo_default)

    env = os.environ.get("SMPL_PATH", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"SMPL_PATH env points to missing file: {p}")

    common_names = [
        "basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
        "SMPL_NEUTRAL.pkl",
        "smpl_neutral.pkl",
        "neutral.pkl",
    ]
    search_dirs = [
        Path.cwd(),
        Path.cwd() / "smpl_models",
        Path.cwd() / "smpl",
        Path.cwd() / "models",
        Path.cwd() / "assets",
        Path.cwd().parent / "smpl_models",
        Path.cwd().parent / "assets",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for name in common_names:
            p = d / name
            if p.exists():
                return str(p)

    raise FileNotFoundError(
        "SMPL model file not found. Provide --smpl_path, or put it at "
        "./smpl_models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl, or set SMPL_PATH."
    )


# -------------------------
# SMPL conversion
# -------------------------
@torch.no_grad()
def smpl_vertices_from_rep272(
    smpl_model: SMPL,
    rep272: np.ndarray,
    yaw_rad: float,
    device: torch.device,
    batch_size: int = 64,
):
    """
    Use 6D rotations to drive SMPL, align pelvis translation to target pelvis position.
    Returns vertices (T,V,3).
    """
    joints_pos, joints_vel, joints_rot6d = rep272_extract(rep272)

    # apply yaw to target joints positions/velocities
    joints_pos = apply_yaw(joints_pos, yaw_rad)
    joints_vel = apply_yaw(joints_vel, yaw_rad)

    T = rep272.shape[0]
    betas = torch.zeros((batch_size, 10), device=device, dtype=torch.float32)

    all_vertices = []
    all_joints22 = []

    for start in range(0, T, batch_size):
        end = min(T, start + batch_size)
        B = end - start

        rot6d = torch.from_numpy(joints_rot6d[start:end]).to(device=device, dtype=torch.float32)  # (B,22,6)
        rotmats = rot6d_to_rotmat(rot6d)  # (B,22,3,3)

        # Apply yaw to root global orient
        if abs(yaw_rad) > 1e-8:
            R_y = torch.from_numpy(rot_yaw_matrix(yaw_rad)).to(device=device, dtype=torch.float32)  # (3,3)
            rotmats[:, 0] = R_y @ rotmats[:, 0]

        global_orient = rotmats[:, 0].unsqueeze(1)  # (B,1,3,3) for smplx pose2rot=False
        body_pose_21 = rotmats[:, 1:]               # (B,21,3,3)

        # pad 2 joints as identity to reach SMPL 23 body joints
        I = torch.eye(3, device=device, dtype=torch.float32).view(1, 1, 3, 3).repeat(B, 2, 1, 1)
        body_pose = torch.cat([body_pose_21, I], dim=1)  # (B,23,3,3)

        # transl=0 to get pelvis
        transl0 = torch.zeros((B, 3), device=device, dtype=torch.float32)
        out0 = smpl_model(
            global_orient=global_orient, body_pose=body_pose, betas=betas[:B], transl=transl0, pose2rot=False
        )
        pelvis0 = out0.joints[:, 0, :]  # (B,3)

        target_pelvis = torch.from_numpy(joints_pos[start:end, 0, :]).to(device=device, dtype=torch.float32)
        transl = target_pelvis - pelvis0

        out = smpl_model(
            global_orient=global_orient, body_pose=body_pose, betas=betas[:B], transl=transl, pose2rot=False
        )

        all_vertices.append(out.vertices.detach().cpu().numpy())
        all_joints22.append(out.joints[:, :22, :].detach().cpu().numpy())

    vertices = np.concatenate(all_vertices, axis=0)
    joints22 = np.concatenate(all_joints22, axis=0)
    return vertices, joints22, joints_pos


# -------------------------
# Video encoding (robust)
# -------------------------
def get_ffmpeg_path() -> Optional[str]:
    return shutil.which("ffmpeg")

def ffmpeg_encoders(ffmpeg_path: str) -> str:
    try:
        p = subprocess.run([ffmpeg_path, "-hide_banner", "-encoders"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return (p.stdout.decode("utf-8", errors="ignore") + "\n" +
                p.stderr.decode("utf-8", errors="ignore"))
    except Exception:
        return ""

def pick_encoder(ffmpeg_path: str) -> List[List[str]]:
    """
    Return a list of command suffixes (after input) to try in order.
    """
    enc = ffmpeg_encoders(ffmpeg_path)
    has_x264 = ("libx264" in enc)
    has_openh264 = ("libopenh264" in enc)

    variants: List[List[str]] = []
    if has_x264:
        variants.append(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17"])
        variants.append(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if has_openh264:
        # openh264 uses QP (lower is better). 28~36 typical.
        variants.append(["-c:v", "libopenh264", "-pix_fmt", "yuv420p", "-qp", "30"])
        variants.append(["-c:v", "libopenh264", "-pix_fmt", "yuv420p"])
    # universal-ish fallback
    variants.append(["-c:v", "mpeg4", "-q:v", "5"])
    return variants

def make_video_ffmpeg(pattern: str, fps: int, out_path: str) -> bool:
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        print("[WARN] ffmpeg not found; skipping mp4 export (PNG frames are saved).")
        return False

    base = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps), "-i", pattern]

    variants = pick_encoder(ffmpeg_path)
    last_err = ""
    for suffix in variants:
        cmd = base + suffix + [out_path]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            return True
        except subprocess.CalledProcessError as e:
            last_err = (e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e))

    print("[WARN] ffmpeg failed to encode mp4; keeping PNG frames only.")
    if last_err:
        tail = "\n".join(last_err.splitlines()[-8:])
        print("[WARN] ffmpeg error tail:\n" + tail)
    return False


# -------------------------
# Rendering
# -------------------------
def render_sequence(
    faces: np.ndarray,
    vertices_seq: np.ndarray,
    out_dir: Path,
    fps: int,
    width: int,
    height: int,
    bg_img: Optional[np.ndarray],
    cam_eye=(0.0, 10.0, 16.0),
    cam_target=(0.0, 1.0, 0.0),
    ambient=0.0,
    light_intensity=3.0,
    auto_offset_mode="center",
    floor_y=0.2,
    fit_screen: bool = False,
    save_frames: bool = False,
):
    out_dir = Path(out_dir)
    masks_dir = out_dir / "masks"
    comp_dir = out_dir / "composites"
    masks_dir.mkdir(parents=True, exist_ok=True)
    comp_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    if save_frames:
        frames_dir.mkdir(parents=True, exist_ok=True)

    T = vertices_seq.shape[0]
    verts = vertices_seq.copy().astype(np.float32)

    # auto offset: keep above floor and centered
    offset = np.zeros(3, dtype=np.float32)
    if auto_offset_mode != "none" or fit_screen:
        min_y = float(np.min(verts[..., 1]))
        offset[1] = floor_y - min_y
        centroid = verts.reshape(T, -1, 3).mean(axis=1)
        if fit_screen:
            # Center trajectory by midpoint of (start,end) so start/end change when length changes.
            mid = 0.5 * (centroid[0] + centroid[-1])
            offset[0] += -float(mid[0])
            offset[2] += -float(mid[2])
        elif auto_offset_mode == "center":
            offset[0] += -float(np.mean(centroid[:, 0]))
            offset[2] += -float(np.mean(centroid[:, 2]))
        elif auto_offset_mode == "enter_from_side":
            dx = float(centroid[-1, 0] - centroid[0, 0])
            start_x_target = 2.0 if dx < 0 else -2.0
            offset[0] += start_x_target - float(centroid[0, 0])
            offset[2] += -float(np.mean(centroid[:, 2]))
        else:
            raise ValueError(f"Unknown auto_offset_mode: {auto_offset_mode}")

    verts += offset[None, None, :]

    # renderer
    renderer = pyrender.OffscreenRenderer(viewport_width=width, viewport_height=height)
    cam_pose = look_at(cam_eye, cam_target, up=(0.0, 1.0, 0.0))
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=float(width) / float(height))
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=light_intensity)

    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[1.0, 1.0, 1.0, 1.0],
        metallicFactor=0.0,
        roughnessFactor=1.0,
        alphaMode="OPAQUE",
        emissiveFactor=[1.0, 1.0, 1.0],
    )

    for t in tqdm(range(T), desc="Render"):
        scene = pyrender.Scene(bg_color=[0.0, 0.0, 0.0, 1.0], ambient_light=[ambient, ambient, ambient])
        mesh_tr = trimesh.Trimesh(vertices=verts[t], faces=faces, process=False)
        mesh = pyrender.Mesh.from_trimesh(mesh_tr, material=material, smooth=False)
        scene.add(mesh)
        scene.add(camera, pose=cam_pose)
        scene.add(light, pose=cam_pose)

        rgb, _ = renderer.render(scene)  # RGB uint8
        mask = (rgb[..., 0] > 10).astype(np.uint8) * 255

        if save_frames:
            cv2.imwrite(str(frames_dir / f"frame_{t:04d}.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(masks_dir / f"mask_{t:04d}.png"), mask)

        if bg_img is None:
            comp = rgb
        else:
            m = (mask.astype(np.float32) / 255.0)[..., None]
            comp = (bg_img.astype(np.float32) * (1.0 - m) + rgb.astype(np.float32) * m).clip(0, 255).astype(np.uint8)

        cv2.imwrite(str(comp_dir / f"composite_{t:04d}.png"), cv2.cvtColor(comp, cv2.COLOR_RGB2BGR))

    renderer.delete()

    # Try mp4 export, but NEVER crash if ffmpeg is limited.
    ok1 = make_video_ffmpeg(str(masks_dir / "mask_%04d.png"), fps, str(out_dir / "mask.mp4"))
    ok2 = make_video_ffmpeg(str(comp_dir / "composite_%04d.png"), fps, str(out_dir / "composite.mp4"))
    if not (ok1 and ok2):
        print("[WARN] mp4 export failed or partially failed; PNG frames are still available.")

    return offset


# -------------------------
# CLI
# -------------------------
def parse_vec3(s: str):
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Expected 'x,y,z'")
    return tuple(parts)

def main():
    global FLIP_TRAJ_LR
    parser = argparse.ArgumentParser(
        description="Render MotionStreamer motion to mask+composite outputs, with controllable yaw.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--motion_npy", type=str, default="", help="Path to motion .npy. If omitted, uses --out_root + --sample_id convention.")
    parser.add_argument("--out_root", type=str, default="runs", help="Root output directory for sample_id convention.")
    parser.add_argument("--sample_id", type=str, default="", help="Sample id for sample_id convention.")
    parser.add_argument("--smpl_path", type=str, default="", help="SMPL pkl path. If omitted, uses ./smpl_models/basicmodel... then $SMPL_PATH then auto-search.")
    parser.add_argument("--out_dir", type=str, default="", help="Output directory. Default: <out_root>/<sample_id>/render_yaw<deg> if sample_id used; else render_out/<motion_stem>_yaw<deg>.")
    parser.add_argument("--input_format", type=str, default="auto", choices=["auto", "joints", "rep272"])
    parser.add_argument("--yaw_deg", type=float, default=0.0, help="Yaw rotation in degrees. + left, - right.")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default= 512)
    parser.add_argument("--height", type=int, default= 512)
    parser.add_argument("--size", type=int, default=None,
                        help="Square output size. If set, overrides --width/--height to size x size.")
    parser.add_argument("--background", type=str, default="", help="Background image path. Empty => black background.")
    parser.add_argument("--cam_eye", type=parse_vec3, default="0,10,16", help="Camera position x,y,z.")
    parser.add_argument("--cam_target", type=parse_vec3, default="0,1,0", help="Camera look-at target x,y,z.")
    parser.add_argument("--ambient", type=float, default=0.0)
    parser.add_argument("--light_intensity", type=float, default=3.0)
    parser.add_argument("--fit_screen", action="store_true", help="Center by full trajectory midpoint (start/end both shift with length/repeat).")
    parser.add_argument("--auto_offset_mode", type=str, default="center", choices=["center", "enter_from_side", "none"])
    parser.add_argument("--floor_y", type=float, default=0.2)
    parser.add_argument("--rep_batch", type=int, default=64)
    parser.add_argument("--save_frames", action="store_true", help="Save debug frames (frames/frame_XXXX.png).")
    parser.add_argument("--save_rotated_npy", type=str, default="", help="If set, save rotated motion to this path.")
    parser.add_argument("--flip_traj_lr", dest="flip_traj_lr", action="store_true", default=True,
                        help="Flip trajectory left-right (negate X) after fit_screen centering (default: on).")
    parser.add_argument("--no_flip_traj_lr", dest="flip_traj_lr", action="store_false",
                        help="Disable trajectory left-right flip.")
    args = parser.parse_args()

    # --- square resolution override ---
    if getattr(args, "size", None):
        args.width = int(args.size)
        args.height = int(args.size)
    FLIP_TRAJ_LR = args.flip_traj_lr
    # Resolve motion path
    if args.motion_npy:
        motion_path = Path(args.motion_npy)
    else:
        if not args.sample_id:
            raise ValueError("Either --motion_npy or --sample_id must be provided.")
        motion_path = resolve_sample_motion(args.out_root, args.sample_id)

    if not motion_path.exists():
        raise FileNotFoundError(f"Motion file not found: {motion_path}")

    # Resolve out_dir
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        if args.sample_id and not args.motion_npy:
            sample_dir = Path(args.out_root) / str(args.sample_id)
            yaw_str = f"{args.yaw_deg:.1f}".replace(".", "p").replace("-", "m")
            out_dir = sample_dir / f"render_yaw{yaw_str}"
        else:
            out_dir = default_out_dir(motion_path, args.yaw_deg)
    out_dir.mkdir(parents=True, exist_ok=True)

    arr = np.load(str(motion_path))
    fmt = args.input_format
    if fmt == "auto":
        fmt = detect_motion_format(arr)

    yaw_rad = float(args.yaw_deg) * np.pi / 180.0

    # Background
    bg: Optional[np.ndarray] = None
    if args.background:
        bg_bgr = load_background_crop(args.background, args.width, args.height)
        bg = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2RGB)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Info] device={device}")

    smpl_path = resolve_smpl_path(args.smpl_path)
    print(f"[Info] using SMPL: {smpl_path}")
    smpl_batch = max(1, min(args.rep_batch, 256))
    smpl = SMPL(smpl_path, batch_size=smpl_batch).to(device)

    if fmt != "rep272":
        raise ValueError("This renderer expects rep272 (T,272) for fast SMPL conversion. Provide motion_272_denorm.npy.")

    verts, joints22, target_joints = smpl_vertices_from_rep272(
        smpl, arr.astype(np.float32), yaw_rad, device, batch_size=smpl_batch
    )
    faces = np.asarray(smpl.faces)


    # ----- Global translation from pelvis trajectory (enables locomotion) -----
    # fit_screen=True: center by trajectory bbox center so start changes with repeat length.
    try:
        T = verts.shape[0]
        _sample_dir = None
        if args.sample_id:
            _sample_dir = Path(args.out_root) / str(args.sample_id)
        elif args.motion_npy:
            _sample_dir = Path(args.motion_npy).resolve().parent
        traj = load_pelvis_traj(Path(_sample_dir), T) if _sample_dir is not None else None
        if traj is not None:
            traj = apply_yaw_to_points(traj, yaw_rad)
            if args.fit_screen:
                bb_min = traj.min(axis=0)
                bb_max = traj.max(axis=0)
                center = 0.5 * (bb_min + bb_max)
                center[1] = 0.0
            else:
                center = traj[0].copy()
                center[1] = 0.0
            traj_centered = traj - center[None, :]
            if FLIP_TRAJ_LR:
                traj_centered[:, 0] *= -1.0  # mirror left-right around anchor center
            verts = verts + traj_centered[:, None, :]
            joints22 = joints22 + traj_centered[:, None, :]
            target_joints = target_joints + traj_centered[:, None, :]
            np.save(str(out_dir / "pelvis_traj_centered.npy"), traj_centered.astype(np.float32))
            print(f"[Info] pelvis_traj centered: start_xz={traj_centered[0,[0,2]]} end_xz={traj_centered[-1,[0,2]]}")
    except Exception as e:
        print("[WARN] pelvis_traj translation failed:", repr(e))

    if args.save_rotated_npy:
        rep = arr.astype(np.float32).copy()
        jpos, jvel, jrot6d = rep272_extract(rep)
        jpos = apply_yaw(jpos, yaw_rad)
        jvel = apply_yaw(jvel, yaw_rad)

        # rotate root rotation
        root6d = jrot6d[:, 0, :]
        rootR = rot6d_to_rotmat(torch.from_numpy(root6d)).cpu().numpy()
        Ry = rot_yaw_matrix(yaw_rad)[None, :, :]
        rootR2 = Ry @ rootR
        jrot6d[:, 0, :] = rotmat_to_rot6d(rootR2)

        rep[:, 8:8+3*22] = jpos.reshape(rep.shape[0], -1)
        rep[:, 8+3*22:8+6*22] = jvel.reshape(rep.shape[0], -1)
        rep[:, 8+6*22:8+12*22] = jrot6d.reshape(rep.shape[0], -1)
        np.save(args.save_rotated_npy, rep)
        print(f"[Info] saved rotated rep272 => {args.save_rotated_npy}")

    offset = render_sequence(
        faces=faces,
        vertices_seq=verts,
        out_dir=out_dir,
        fps=args.fps,
        width=args.width,
        height=args.height,
        bg_img=bg,
        cam_eye=args.cam_eye,
        cam_target=args.cam_target,
        ambient=args.ambient,
        light_intensity=args.light_intensity,
        auto_offset_mode=args.auto_offset_mode,
        floor_y=args.floor_y,
        fit_screen=args.fit_screen,
        save_frames=args.save_frames,
    )

    print(f"[Done] outputs in: {out_dir}")
    print(f"       - masks/: {out_dir/'masks'}")
    print(f"       - composites/: {out_dir/'composites'}")
    print(f"       - mask.mp4 (best effort): {out_dir/'mask.mp4'}")
    print(f"       - composite.mp4 (best effort): {out_dir/'composite.mp4'}")
    print(f"[Info] applied render offset (x,y,z): {offset.tolist()}")


if __name__ == "__main__":
    main()
