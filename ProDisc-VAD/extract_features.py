"""Extract ten CLIP crop streams in the format used by the ProDisc-VAD loaders."""
import argparse
import fcntl
import io
import os
from pathlib import Path
import random
import re

import cv2
import numpy as np
from PIL import Image
import torch


PROTOCOLS = {
    "shanghaitech": {
        "label": "ShanghaiTech", "dtype": "float32", "frame_interval": 16,
        "feature_folder": "SH_clip_video_features",
        "description": "Video or numbered frame folder, ten float32 crop streams.",
        "status": "ProDisc-VAD feature layout with the public VadCLIP crop order. Historical frame offset is undocumented.",
    },
    "ucf-crime": {
        "label": "UCF-Crime", "dtype": "float16", "frame_interval": 16,
        "feature_folder": "UCFClipFeatures",
        "description": "Video file, ten float16 crop streams.",
        "status": "VadCLIP crop order and sampling stride. Historical frame offset is undocumented.",
    },
}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def get_protocol(dataset):
    if dataset not in PROTOCOLS:
        raise ValueError("dataset must be shanghaitech or ucf-crime")
    return PROTOCOLS[dataset]


def load_clip_encoder(dataset, device):
    """Use float32 for ShanghaiTech and CLIP's native CUDA precision for UCF-Crime."""
    import clip

    protocol = get_protocol(dataset)
    random.seed(1)
    np.random.seed(1)
    torch.manual_seed(1)
    model, preprocess = clip.load("ViT-B/16", device=device)
    if protocol["dtype"] == "float32" or torch.device(device).type == "cpu":
        model.float()
    return model.eval(), preprocess


def feature_targets(output_dir, sample_id):
    if not isinstance(sample_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sample_id):
        raise ValueError("Sample ID must contain 1-128 letters, digits, underscores or hyphens")
    targets = [Path(output_dir) / f"{sample_id}_{crop}.npy" for crop in range(10)]
    if any(path.is_symlink() for path in targets):
        raise FileExistsError(f"Feature name already in use: {sample_id}")
    if all(path.is_file() for path in targets):
        try:
            for path in targets:
                np.load(path, mmap_mode="r", allow_pickle=False)
        except (EOFError, ValueError):
            return targets
        raise FileExistsError(f"Feature already exists: {sample_id}")
    return targets


def spatial_crops(frame):
    """Follow VadCLIP's crop order: center, TL, TR, BL, BR, then their horizontal flips."""
    resized = cv2.cvtColor(cv2.resize(frame, (340, 256), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
    crops = [
        resized[16:240, 58:282],
        resized[:224, :224], resized[:224, -224:],
        resized[-224:, :224], resized[-224:, -224:],
    ]
    return crops + [cv2.flip(crop, 1) for crop in crops]


@torch.inference_mode()
def encode_frame_crops(frame, model, preprocess, device, dataset):
    """Encode the ten spatial views of a single representative BGR frame."""
    batch = torch.stack([preprocess(Image.fromarray(crop)) for crop in spatial_crops(frame)])
    encoded = model.encode_image(batch.to(device)).cpu().numpy().astype(get_protocol(dataset)["dtype"], copy=False)
    if encoded.shape != (10, 512) or not np.isfinite(encoded).all():
        raise ValueError("Expected finite CLIP ViT-B/16 features with shape (10, 512)")
    return encoded


def _natural_key(path):
    return [(1, int(part)) if part.isdigit() else (0, part.lower())
            for part in re.split(r"(\d+)", path.name)]


def validate_source(source, dataset):
    get_protocol(dataset)
    source = Path(source)
    if source.is_dir():
        if dataset != "shanghaitech":
            raise ValueError("UCF-Crime requires a video file")
        if not any(p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES for p in source.iterdir()):
            raise ValueError("Frame folder contains no supported images")
    elif not source.is_file():
        raise FileNotFoundError(f"Source not found: {source}")
    elif source.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError("Unsupported video format")
    return source


def _frames(source, metadata):
    if source.is_dir():
        paths = sorted((p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES), key=_natural_key)
        metadata["fps"] = None
        for path in paths:
            frame = cv2.imread(str(path))
            if frame is None:
                raise ValueError(f"Cannot decode frame: {path.name}")
            metadata["total_frames"] += 1
            yield frame
    else:
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            cap.release()
            raise ValueError(f"Cannot open video: {source.name}")
        metadata["fps"] = cap.get(cv2.CAP_PROP_FPS)
        expected = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                metadata["total_frames"] += 1
                yield frame
            if expected > 0 and metadata["total_frames"] < expected:
                raise ValueError("Video decoding stopped before the declared frame count")
        finally:
            cap.release()


def extract_clip_features(source, model, preprocess, device, dataset):
    """Return one unnormalized embedding sequence per spatial view."""
    protocol = get_protocol(dataset)
    source = validate_source(source, dataset)
    metadata = {"total_frames": 0, "fps": None}
    features = []
    interval = protocol["frame_interval"]
    for index, frame in enumerate(_frames(source, metadata)):
        if index % interval == 0:
            first_frame = frame
        if (index + 1) % interval == 0:
            features.append(encode_frame_crops(first_frame, model, preprocess, device, dataset))
    if not features:
        raise ValueError(f"At least {interval} decoded frames are required for one feature segment")
    # Keep the crop dimension intact while joining the time steps.
    metadata["features"] = np.stack(features, axis=1)
    metadata["dataset"] = dataset
    metadata["protocol"] = dict(protocol)
    metadata["feature_frames"] = len(features)
    metadata["feature_shape"] = [len(features), 512]
    metadata["num_crops"] = 10
    return metadata


def save_features(features, output_dir, sample_id):
    if (features.ndim != 3 or features.shape[0] != 10
            or features.shape[1] == 0 or features.shape[2] != 512):
        raise ValueError("Expected ten crop streams with shape (10, T, 512)")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    directory_fd = os.open(output_dir, os.O_RDONLY)
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX)
        targets = feature_targets(output_dir, sample_id)
        pending = []
        for crop, target in zip(features, targets):
            if target.exists():
                try:
                    saved = np.load(target, allow_pickle=False)
                    matches = saved.dtype == crop.dtype and np.array_equal(saved, crop)
                except (EOFError, ValueError):
                    # An interrupted older writer can leave a prefix of the intended .npy file.
                    encoded = io.BytesIO()
                    np.save(encoded, crop, allow_pickle=False)
                    if encoded.getvalue().startswith(target.read_bytes()):
                        pending.append((crop, target))
                        continue
                    matches = False
                if not matches:
                    raise FileExistsError(f"Existing crop differs from this extraction: {target.name}")
            else:
                pending.append((crop, target))

        # Publish only fully written crops. A retry reuses this private staging path.
        stage = output_dir / f".{sample_id}.pending"
        for crop, target in pending:
            with stage.open("wb") as stream:
                np.save(stream, crop, allow_pickle=False)
            stage.replace(target)
    finally:
        os.close(directory_fd)
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=PROTOCOLS)
    parser.add_argument("--video", required=True, type=Path, help="Video file, or ShanghaiTech frame folder")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sample-id", required=True)
    args = parser.parse_args()
    validate_source(args.video, args.dataset)
    feature_targets(args.output_dir, args.sample_id)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = load_clip_encoder(args.dataset, device)
    result = extract_clip_features(args.video, model, preprocess, device, args.dataset)
    features = result.pop("features")
    save_features(features, args.output_dir, args.sample_id)
    print(f"Saved 10 crops: {args.sample_id}, {result['feature_shape']}, {features.dtype}")


if __name__ == "__main__":
    main()
