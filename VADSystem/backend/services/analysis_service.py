"""Analysis Service - Results Analysis and Visualization"""
import os
import importlib.util
import sys
import pickle
import re
from pathlib import Path
from urllib.parse import quote
import numpy as np
from typing import Optional, Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import REPO_ROOT, PRODISC_VAD_PATH, DATASET_PATH, MODELS, CKPT_PATH

# The standalone detector and the Flask backend both have a module named utils.
_spec = importlib.util.spec_from_file_location("prodisc_utils", Path(REPO_ROOT) / "ProDisc-VAD" / "utils.py")
prodisc_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prodisc_utils)


read_test_videos = prodisc_utils.read_test_videos
evaluate_frames = prodisc_utils.evaluate_frames


def _run_measurements(file):
    parameters = {}
    points = {}
    if file and file.is_file():
        with file.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = re.fullmatch(r"(?:Iteration: (\d+) Area Under the Curve is |itration_(\d+)_AUC is )([0-9.eE+-]+)", line.strip())
                if match:
                    iteration = int(match[1] or match[2])
                    try:
                        auc = float(match[3])
                    except ValueError:
                        continue
                    if 0 <= auc <= 1:
                        points[iteration] = auc
                else:
                    key, _, value = line.partition(":")
                    if key in {"dataset_name", "model_name", "run_id", "sample_size", "synthetic_samples", "synthetic_ratio"}:
                        parameters[key] = value.strip()
    iterations = sorted(points)
    return parameters, iterations, [points[i] for i in iterations]


def _recorded_synthetic_group(params):
    """Read the class-bag sampling configuration recorded for a run."""
    samples = params.get("synthetic_samples")
    if samples is not None and (samples == "None" or not any(s.strip() for s in samples.split(","))):
        return False
    try:
        ratio = float(params["synthetic_ratio"])
        if not 0 <= ratio <= 1:
            return None
        if ratio == 0:
            return False
        if samples is None:
            return None
        if "sample_size" not in params:
            return True if ratio == 1 else None
        size = int(params["sample_size"])
        return int(size * ratio) > 0 if size > 0 else None
    except (KeyError, ValueError):
        return None


def model_runs():
    """Associate each checkpoint with its own result file or explicitly paired log."""
    root = Path(CKPT_PATH)
    project = Path(PRODISC_VAD_PATH)
    checkpoints = {p.parent: p for p in sorted(root.glob("**/final_model.pkl"))}
    checkpoints.update({p.parent: p for p in sorted(root.glob("**/best_model.pkl"))})
    paths = []
    for key, preset in MODELS.items():
        configured = Path(preset["path"])
        candidates = [d for d in checkpoints if d.parent == root / preset["name"]]
        directory = configured.parent
        if directory not in checkpoints and len(candidates) == 1:
            directory = candidates[0]
        if directory in checkpoints or not candidates:
            paths.append((key, checkpoints.pop(directory, configured), preset, len(candidates) <= 1))
    for directory, path in sorted(checkpoints.items()):
        rel = directory.relative_to(root)
        run_id = "run:" + ":".join(quote(part, safe="") for part in rel.parts)
        paths.append((run_id, path, {}, False))

    for run_id, path, preset, use_preset_log in paths:
        rel = path.parent.relative_to(root) if path.is_relative_to(root) else None
        name = preset["name"] if preset else rel.as_posix()
        result_file = project / "result" / rel / "result.txt" if rel is not None else None
        if rel is not None and not result_file.is_file():
            result_file = project / "logs" / rel.parent / (rel.name + ".log")
        params, iterations, values = _run_measurements(result_file)
        if use_preset_log and preset.get("log_path") and (result_file is None or not result_file.is_file()):
            flat_log = Path(preset["log_path"])
            flat_params, flat_steps, flat_values = _run_measurements(flat_log)
            if (flat_params.get("run_id") == path.parent.name
                    and flat_params.get("model_name", preset["name"]) == preset["name"]):
                params, iterations, values = flat_params, flat_steps, flat_values
                result_file = flat_log
        dataset = params.get("dataset_name") or preset.get("dataset")
        name_lower = name.lower()
        if not dataset:
            if "sht" in name_lower or "shanghaitech" in name_lower or "sh_" in name_lower:
                dataset = "shanghaitech"
            elif "ucf" in name_lower:
                dataset = "ucf-crime"
        synthetic = _recorded_synthetic_group(params)
        final_only = path.name == "final_model.pkl"
        yield {
            "id": run_id, "name": name + " (final)" if final_only else name, "dataset": dataset, "synthetic": synthetic,
            "path": str(path), "available": path.is_file(), "is_preset": bool(preset),
            "record_path": str(result_file) if result_file and result_file.is_file() else None,
            "iterations": iterations, "auc_values": values, "auc": None if final_only else max(values, default=None),
            "iters": iterations[-1] if iterations else None
        }


def find_model_run(runs, model_id):
    legacy_matches = []
    for run in runs:
        if run["id"] == model_id:
            return run
        directory = Path(run["path"]).parent
        if directory.is_relative_to(CKPT_PATH):
            rel = directory.relative_to(CKPT_PATH)
            run_alias = "run:" + ":".join(quote(part, safe="") for part in rel.parts)
            if model_id in (run_alias, "trained_" + "_".join(rel.parts)):
                legacy_matches.append(run)
    return legacy_matches[0] if len(legacy_matches) == 1 else None


class AnalysisService:
    """Service for analyzing anomaly detection results"""
    
    def __init__(self):
        self.gt_cache: Dict[str, dict] = {}
    
    def _load_ground_truth(self, dataset: str) -> dict:
        """Load ground truth labels for dataset"""
        cache_key = dataset
        if cache_key in self.gt_cache:
            return self.gt_cache[cache_key]
        
        gt_data = {
            "video_labels": {},
            "frame_labels": {}
        }
        
        if dataset == 'shanghaitech':
            gt_dir = os.path.join(DATASET_PATH, "shanghaitech", "GT")
            
            # Load video labels
            video_label_path = os.path.join(gt_dir, "video_label_10crop.pickle")
            if os.path.exists(video_label_path):
                with open(video_label_path, 'rb') as f:
                    gt_data["video_labels"] = pickle.load(f)
            
            # Load frame labels
            frame_label_path = os.path.join(gt_dir, "frame_label.pickle")
            if os.path.exists(frame_label_path):
                with open(frame_label_path, 'rb') as f:
                    gt_data["frame_labels"] = pickle.load(f)
        
        else:  # UCF-Crime
            gt_dir = os.path.join(DATASET_PATH, "ucf-crime", "GT")
            
            # Load video labels
            video_label_path = os.path.join(gt_dir, "video_label_10crop.pickle")
            if os.path.exists(video_label_path):
                with open(video_label_path, 'rb') as f:
                    gt_data["video_labels"] = pickle.load(f)
            
            # Load frame labels
            frame_label_path = os.path.join(gt_dir, "ucf_gt_upgate.pickle")
            if os.path.exists(frame_label_path):
                with open(frame_label_path, 'rb') as f:
                    gt_data["frame_labels"] = pickle.load(f)
        
        self.gt_cache[cache_key] = gt_data
        return gt_data
    
    def calculate_auc(
        self,
        predictions: Dict[str, List[float]],
        ground_truth: Dict[str, List[int]] = None,
        dataset: str = 'shanghaitech'
    ) -> dict:
        """Use the same test membership and frame alignment as the training evaluator."""
        try:
            if ground_truth is None:
                videos = read_test_videos(Path(DATASET_PATH) / dataset / "test_split_10crop.txt")
                labels = self._load_ground_truth(dataset)
                result = evaluate_frames(predictions, labels["frame_labels"], videos,
                                         labels["video_labels"], with_roc=True)
                scope = "standard"
            else:
                result = evaluate_frames(predictions, ground_truth, list(ground_truth), with_roc=True)
                scope = "custom"
            return {"success": True, "scope": scope, **result}
        except (OSError, TypeError, ValueError) as error:
            return {"success": False, "error": str(error)}

    def compare_models(
        self,
        model_results: Dict[str, Dict[str, List[float]]],
        dataset: str = 'shanghaitech'
    ) -> dict:
        """Compare AUC scores from multiple models"""
        comparison = {}
        
        for model_id, predictions in model_results.items():
            result = self.calculate_auc(predictions, dataset=dataset)
            
            if result.get("success"):
                model_name = MODELS.get(model_id, {}).get("name", model_id)
                comparison[model_id] = {
                    "name": model_name,
                    "auc": result["auc"],
                    "num_videos": result["num_videos"]
                }
            else:
                comparison[model_id] = {"error": result.get("error")}
        
        # Sort by AUC
        sorted_models = sorted(
            [(k, v) for k, v in comparison.items() if "auc" in v],
            key=lambda x: x[1]["auc"],
            reverse=True
        )
        
        return {
            "success": True,
            "comparison": comparison,
            "ranking": [{"model_id": k, **v} for k, v in sorted_models]
        }
    
    def get_frame_scores(
        self,
        video_name: str,
        predictions: List[float]
    ) -> dict:
        """Get frame-level anomaly scores for visualization"""
        # Expand to frame level
        frame_scores = np.repeat(predictions, 16)
        
        # Normalize to [0, 1]
        min_score = float(np.min(frame_scores))
        max_score = float(np.max(frame_scores))
        
        if max_score > min_score:
            normalized_scores = (frame_scores - min_score) / (max_score - min_score)
        else:
            normalized_scores = np.zeros_like(frame_scores)
        
        # Find anomaly peaks
        threshold = 0.5
        anomaly_regions = []
        in_anomaly = False
        start_frame = 0
        
        for i, score in enumerate(normalized_scores):
            if score > threshold and not in_anomaly:
                in_anomaly = True
                start_frame = i
            elif score <= threshold and in_anomaly:
                in_anomaly = False
                anomaly_regions.append({
                    "start": start_frame,
                    "end": i,
                    "peak_score": float(max(normalized_scores[start_frame:i]))
                })
        
        if in_anomaly:
            anomaly_regions.append({
                "start": start_frame,
                "end": len(normalized_scores),
                "peak_score": float(max(normalized_scores[start_frame:]))
            })
        
        return {
            "success": True,
            "video_name": video_name,
            "num_frames": len(frame_scores),
            "scores": frame_scores.tolist(),
            "normalized_scores": normalized_scores.tolist(),
            "min_score": min_score,
            "max_score": max_score,
            "anomaly_regions": anomaly_regions
        }

    def get_infer_score_plot(
        self,
        dataset: str,
        model_id: str,
        video_name: str = None
    ) -> dict:
        """Run standard test-set inference and return aligned scores with GT regions."""
        default_videos = {
            "shanghaitech": "01_0025",
            "ucf-crime": "Robbery050_x264",
        }
        target_video = video_name or default_videos.get(dataset)
        if not target_video:
            return {"error": f"No default inference video configured for dataset: {dataset}"}

        from services.infer_service import InferService

        infer_result = InferService().predict(target_video, model_id)
        if not infer_result.get("success"):
            return infer_result
        if infer_result["dataset"] != dataset:
            return {"error": "Selected model belongs to a different dataset"}

        gt_data = self._load_ground_truth(dataset)
        frame_labels = gt_data["frame_labels"].get(target_video)
        if frame_labels is None:
            return {"error": f"Ground truth not found for video: {target_video}"}

        segment_scores = np.asarray(infer_result["scores"], dtype=np.float32)
        frame_scores = np.repeat(segment_scores, 16)
        labels = (np.asarray(frame_labels, dtype=np.float32) >= 0.5).astype(np.int32)
        aligned_len = min(len(frame_scores), len(labels))
        frame_scores = frame_scores[:aligned_len]
        labels = labels[:aligned_len]

        gt_regions = []
        region_start = None
        for idx, label in enumerate(labels):
            if label > 0 and region_start is None:
                region_start = idx
            elif label <= 0 and region_start is not None:
                gt_regions.append({"start_frame": region_start, "end_frame": idx})
                region_start = None
        if region_start is not None:
            gt_regions.append({"start_frame": region_start, "end_frame": aligned_len})

        return {
            "success": True,
            "dataset": dataset,
            "video_name": infer_result["video_name"],
            "model_id": model_id,
            "num_segments": len(segment_scores),
            "num_frames": aligned_len,
            "scores": segment_scores.tolist(),
            "frame_scores": frame_scores.tolist(),
            "frame_labels": labels.tolist(),
            "gt_regions": gt_regions,
            "max_score": float(np.max(segment_scores)),
            "mean_score": float(np.mean(segment_scores)),
            "crop_names": infer_result.get("crop_names", []),
        }
    
    def generate_heatmap(
        self,
        video_name: str,
        predictions: List[float]
    ) -> dict:
        """Generate heatmap data for anomaly visualization"""
        frame_scores = np.repeat(predictions, 16)
        
        # Create heatmap data (downsample for visualization)
        num_bins = min(100, len(frame_scores))
        bin_size = len(frame_scores) // num_bins
        
        heatmap_data = []
        for i in range(num_bins):
            start_idx = i * bin_size
            end_idx = min((i + 1) * bin_size, len(frame_scores))
            bin_scores = frame_scores[start_idx:end_idx]
            
            heatmap_data.append({
                "bin": i,
                "start_frame": start_idx,
                "end_frame": end_idx,
                "mean_score": float(np.mean(bin_scores)),
                "max_score": float(np.max(bin_scores)),
                "min_score": float(np.min(bin_scores))
            })
        
        return {
            "success": True,
            "video_name": video_name,
            "num_bins": num_bins,
            "total_frames": len(frame_scores),
            "heatmap": heatmap_data
        }
    
    def get_ground_truth(
        self,
        dataset: str = 'shanghaitech',
        video_name: str = None
    ) -> dict:
        """Get ground truth labels"""
        gt_data = self._load_ground_truth(dataset)
        
        if video_name:
            video_label = gt_data["video_labels"].get(video_name + "_0")
            labels = gt_data["frame_labels"].get(video_name)
            return {
                "video_name": video_name, "video_label": video_label,
                "frame_labels": np.asarray(labels).tolist() if labels is not None else None,
                "is_anomaly": video_label == "[1.0]" if video_label is not None else None,
                "num_frames": len(labels) if labels is not None else None
            }

        split = Path(DATASET_PATH) / dataset / "test_split_10crop.txt"
        counts = dict(total_videos=None, anomaly_videos=None, normal_videos=None, videos_with_frame_labels=None)
        if split.is_file():
            with split.open() as stream:
                videos = {line.strip().rsplit("_", 1)[0] for line in stream if line.strip()}
            labels = [gt_data["video_labels"].get(video + "_0") for video in videos]
            counts.update(total_videos=len(videos), videos_with_frame_labels=len(videos.intersection(gt_data["frame_labels"])))
            if all(label in ("[0.0]", "[1.0]") for label in labels):
                counts.update(anomaly_videos=labels.count("[1.0]"), normal_videos=labels.count("[0.0]"))
        return {"dataset": dataset, **counts}

    def get_training_curve(self, model_id: str) -> dict:
        run = find_model_run(list(model_runs()), model_id)
        if run is None or not run["iterations"]:
            return {"error": "No evaluation log for this run"}
        return {
            "success": True, "model_id": run["id"], "model_name": run["name"],
            "iterations": run["iterations"], "auc_values": run["auc_values"],
            "final_auc": run["auc_values"][-1], "best_auc": max(run["auc_values"]), "total_iters": run["iters"]
        }

    def get_comparison_data(self, dataset: str = "shanghaitech") -> dict:
        result = {"success": True, "dataset": dataset, "models": [], "curves": {},
                  "ground_truth": self.get_ground_truth(dataset)}
        for run in model_runs():
            if run["dataset"] != dataset:
                continue
            result["models"].append({key: value for key, value in run.items()
                                     if key not in ("path", "record_path", "iterations", "auc_values")})
            if run["iterations"]:
                result["curves"][run["id"]] = {"iterations": run["iterations"], "auc_values": run["auc_values"]}
        result["models"].sort(key=lambda m: (m["auc"] is None, -(m["auc"] or 0), m["name"]))
        return result

    def get_summary(self, dataset: str = "shanghaitech") -> dict:
        """Summarize recorded peaks. The signed difference compares the two group peaks."""
        summary = self.get_comparison_data(dataset)
        summary.pop("curves")
        scored = [m for m in summary["models"] if m["auc"] is not None]
        baseline = next((m["auc"] for m in scored if m["synthetic"] is False), None)
        augmented = next((m["auc"] for m in scored if m["synthetic"] is True), None)
        summary.update(
            total_videos=summary["ground_truth"]["total_videos"],
            best_auc=scored[0]["auc"] if scored else None,
            best_model=scored[0]["name"] if scored else None, baseline_auc=baseline,
            improvement=augmented - baseline if augmented is not None and baseline is not None else None
        )
        return summary
