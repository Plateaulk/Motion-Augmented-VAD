"""Inference Service - Anomaly Detection"""
import os
import sys
from pathlib import Path
import numpy as np
import torch
from typing import Optional, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PRODISC_VAD_PATH, DATASET_PATH, MODELS, SHT_FEATURE_PATH, UCF_FEATURE_PATH
)

from services.analysis_service import model_runs, find_model_run, prodisc_utils, read_test_videos

# Add ProDisc-VAD for model imports without shadowing backend packages such as utils.
if PRODISC_VAD_PATH not in sys.path:
    sys.path.append(PRODISC_VAD_PATH)


class InferService:
    """Service for anomaly detection inference"""
    _loaded_models: Dict[str, Tuple[int, torch.nn.Module]] = {}
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.loaded_models = self.__class__._loaded_models
        self.feature_size = 512
        self.max_seqlen = 300
    
    def _load_model(self, model_id: str, run=None) -> Optional[torch.nn.Module]:
        if run is None:
            run = find_model_run(model_runs(), model_id)
        if run is None or not run["available"]:
            return None
        path = run["path"]
        modified = os.stat(path).st_mtime_ns
        cached = self.loaded_models.get(path)
        if cached is not None and cached[0] == modified:
            return cached[1]
        try:
            from ProDisc_VAD import ProDisc_VAD
            model = ProDisc_VAD(feature_size=self.feature_size).to(self.device)
            model.load_state_dict(torch.load(path, map_location=self.device))
            model.eval()
            self.loaded_models[path] = (modified, model)
            return model
        except Exception as e:
            print(f"Failed to load model {model_id}: {e}")
            return None

    def list_models(self) -> List[dict]:
        return [{key: value for key, value in run.items() if key not in ("iterations", "auc_values", "record_path")}
                for run in model_runs()]

    def _feature_dir(self, dataset: str) -> str:
        if dataset == 'shanghaitech':
            return SHT_FEATURE_PATH
        return UCF_FEATURE_PATH

    def _test_split_path(self, dataset: str) -> str:
        return os.path.join(DATASET_PATH, dataset, "test_split_10crop.txt")

    @staticmethod
    def _base_video_name(video_name: str) -> str:
        stem = os.path.splitext(os.path.basename(video_name))[0]
        if '_' not in stem:
            return stem
        base, suffix = stem.rsplit('_', 1)
        return base if len(suffix) == 1 and suffix.isdigit() else stem

    def _load_crop_group(self, directory, base_name):
        names = [f"{base_name}_{crop}" for crop in range(10)]
        features = [prodisc_utils.load_feature(Path(directory) / (name + ".npy"), self.feature_size)
                    for name in names]
        if len({feature.shape for feature in features}) != 1:
            raise ValueError(f"Ten crop streams have different lengths: {base_name}")
        return np.stack(features), names

    def _predict_feature_batch(self, model: torch.nn.Module, feature_batch: np.ndarray) -> Tuple[np.ndarray, int, int]:
        if (feature_batch.ndim != 3 or feature_batch.shape[0] != 10 or feature_batch.shape[1] == 0
                or feature_batch.shape[2] != self.feature_size
                or not np.issubdtype(feature_batch.dtype, np.floating) or not np.isfinite(feature_batch).all()):
            raise ValueError("Expected ten finite floating crop streams with shape (10, T, 512)")

        feature_tensor = torch.from_numpy(feature_batch.astype(np.float32)).to(self.device)
        seq_len = torch.sum(torch.max(torch.abs(feature_tensor), dim=2)[0] > 0, 1)

        with torch.no_grad():
            _, element_scores, _ = model(feature_tensor, seq_len, is_training=False)
            scores = torch.mean(element_scores, dim=0).cpu().numpy().reshape(-1)

        return scores, int(feature_batch.shape[1]), int(feature_batch.shape[0])
    
    def predict(
        self, 
        video_name: str, 
        model_id: str,
        feature_path: str = None, *, run=None
    ) -> dict:
        """Run inference on a video"""
        if run is None:
            run = find_model_run(model_runs(), model_id)
        if run is None:
            return {"error": f"Unknown or ambiguous model: {model_id}"}
        model = self._load_model(model_id, run)
        if model is None:
            return {"error": f"Model not found or failed to load: {model_id}"}
        
        dataset = run["dataset"]
        if dataset is None and not feature_path:
            return {"error": f"No dataset recorded for model: {model_id}"}

        try:
            if feature_path:
                path = Path(feature_path)
                feature = np.load(path, mmap_mode="r", allow_pickle=False)
                if feature.ndim == 3:
                    feature_batch, crop_names = feature, [path.name]
                else:
                    base = self._base_video_name(path.name)
                    if path.suffix != ".npy" or base == path.stem:
                        raise ValueError("Select a numbered crop file or a stacked (10, T, 512) feature")
                    feature_batch, crop_names = self._load_crop_group(path.parent, base)
                output_video_name = video_name
            else:
                videos = self.list_videos(dataset)
                output_video_name = video_name if video_name in videos else self._base_video_name(video_name)
                if output_video_name not in videos:
                    raise ValueError(f"Video missing from the standard test split: {video_name}")
                feature_batch, crop_names = self._load_crop_group(self._feature_dir(dataset), output_video_name)
            scores, original_len, num_crops = self._predict_feature_batch(model, feature_batch)
        except (OSError, ValueError, EOFError) as error:
            return {"error": str(error)}

        # Expand scores to match original frame count
        # Each score represents 16 frames
        frame_scores = np.repeat(scores, 16)[:original_len * 16]
        
        return {
            "success": True,
            "video_name": output_video_name,
            "dataset": dataset,
            "model_id": model_id,
            "scores": scores.tolist(),
            "frame_scores": frame_scores.tolist(),
            "num_segments": len(scores),
            "original_feature_len": original_len,
            "num_crops": num_crops,
            "crop_names": crop_names,
            "max_score": float(np.max(scores)),
            "mean_score": float(np.mean(scores))
        }
    
    def predict_batch(
        self, 
        video_names: List[str], 
        model_id: str
    ) -> dict:
        """Run batch inference, returns results as array with frontend-compatible fields"""
        results = []
        errors = []
        run = find_model_run(model_runs(), model_id)
        for video_name in video_names:
            result = self.predict(video_name, model_id, run=run)
            if result.get("success"):
                results.append({
                    "video_id": video_name,
                    "video_name": video_name,
                    "is_anomaly": result["max_score"] > 0.5,
                    "avg_score": result["mean_score"],
                    "max_score": result["max_score"],
                    "scores": result.get("scores", []),
                    "num_segments": result.get("num_segments", 0)
                })
            else:
                errors.append({"video_name": video_name, "error": result.get("error", "unknown")})
        
        # Sort by anomaly score, highest first
        results.sort(key=lambda x: x["max_score"], reverse=True)
        
        return {
            "success": True,
            "model_id": model_id,
            "total": len(video_names),
            "completed": len(results),
            "errors": len(errors),
            "results": results
        }
    
    def compare_models(
        self, 
        video_name: str, 
        model_ids: List[str]
    ) -> dict:
        """Compare predictions from multiple models"""
        results = {}
        
        for model_id in model_ids:
            result = self.predict(video_name, model_id)
            if result.get("success"):
                results[model_id] = {
                    "name": MODELS.get(model_id, {}).get("name", model_id),
                    "scores": result["scores"],
                    "max_score": result["max_score"],
                    "mean_score": result["mean_score"]
                }
            else:
                results[model_id] = {"error": result.get("error")}
        
        return {
            "success": True,
            "video_name": video_name,
            "models": results
        }
    
    def list_videos(self, dataset: str = 'shanghaitech') -> List[str]:
        """List standard test videos in the same order used during training evaluation."""
        path = self._test_split_path(dataset)
        return read_test_videos(path) if os.path.isfile(path) else []
