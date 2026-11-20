"""Training Service"""
import os
import sys
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PRODISC_VAD_PATH, CKPT_PATH, SHT_FEATURE_PATH, UCF_FEATURE_PATH,
    DEFAULT_SYNTHETIC_RATIOS
)
from utils.process_manager import get_training_manager


class TrainService:
    """Service for model training"""
    
    def __init__(self):
        self.manager = get_training_manager()
    
    def start_training(
        self,
        dataset: str = 'shanghaitech',
        seed: int = 1,
        max_iters: int = 600,
        k: int = 5,
        synthetic_samples: str = None,
        synthetic_ratio: Optional[float] = None,
        model_name: str = None,
        sample_size: int = 30,
        lr: float = 0.0005,
        batch_size: int = 1,
        snapshot: int = 1,
        plot: int = 0
    ) -> dict:
        """Start a training job"""
        if self.manager.is_training():
            return {
                "success": False,
                "error": "A training job is already running",
                "current_job": self.manager.current_job
            }
        
        if synthetic_ratio is None:
            synthetic_ratio = DEFAULT_SYNTHETIC_RATIOS[dataset]

        # Generate job ID and model name
        job_id = str(uuid.uuid4())[:8]
        
        if model_name is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            synthetic_tag = "synthetic" if synthetic_samples and int(sample_size * synthetic_ratio) > 0 else "baseline"
            model_name = f"{dataset}_{synthetic_tag}_seed{seed}_{timestamp}"
        
        # Auto-suffix model dir if it already exists
        original_name = model_name
        model_dir = os.path.join(CKPT_PATH, model_name)
        counter = 1
        while os.path.exists(model_dir):
            counter += 1
            model_name = f"{original_name}_{counter}"
            model_dir = os.path.join(CKPT_PATH, model_name)
        
        # Start training
        success = self.manager.start_training(
            job_id=job_id,
            dataset=dataset,
            seed=seed,
            max_iters=max_iters,
            k=k,
            synthetic_samples=synthetic_samples,
            synthetic_ratio=synthetic_ratio,
            model_name=model_name,
            sample_size=sample_size,
            lr=lr,
            batch_size=batch_size,
            snapshot=snapshot,
            plot=plot
        )
        
        if success:
            return {
                "success": True,
                "job_id": job_id,
                "model_name": model_name,
                "config": {
                    "dataset": dataset,
                    "seed": seed,
                    "max_iters": max_iters,
                    "k": k,
                    "synthetic_samples": synthetic_samples,
                    "synthetic_ratio": synthetic_ratio,
                    "sample_size": sample_size,
                    "lr": lr,
                    "batch_size": batch_size
                }
            }
        else:
            return {
                "success": False,
                "error": "Failed to start training job"
            }
    
    def stop_training(self) -> dict:
        """Stop current training job"""
        if not self.manager.is_training():
            return {
                "success": False,
                "error": "No training job is running"
            }
        
        job_id = self.manager.current_job
        success = self.manager.stop_training()
        
        return {
            "success": success,
            "job_id": job_id,
            "message": "Training stopped" if success else "Failed to stop training"
        }
    
    def get_status(self) -> dict:
        """Get training status - returns frontend-compatible format"""
        raw = self.manager.get_status()
        is_running = raw.get("status") == "running"
        metrics = raw.get("metrics", [])
        current_iter = 0
        current_auc = None
        if metrics:
            current_iter = metrics[-1].get("iteration", 0)
            current_auc = metrics[-1].get("auc")
        return {
            "running": is_running,
            "current_iter": current_iter,
            "total_iters": self.manager.total_iters,
            "current_auc": current_auc,
            "best_auc": raw.get("best_auc"),
            "job_id": raw.get("job_id"),
            "metrics": metrics
        }
    
    def get_logs(self, n: int = 100) -> List[str]:
        """Get recent training logs"""
        return self.manager.get_logs(n)
    
    def list_models(self) -> List[dict]:
        """List all trained models with file details"""
        from services.analysis_service import model_runs
        models = []
        runs_by_folder = {}
        for run in model_runs():
            if run["available"]:
                folder = Path(run["path"]).relative_to(CKPT_PATH).parts[0]
                runs_by_folder.setdefault(folder, []).append(run)
        
        if os.path.exists(CKPT_PATH):
            for model_dir in os.listdir(CKPT_PATH):
                model_path = os.path.join(CKPT_PATH, model_dir)
                if os.path.isdir(model_path):
                    runs = runs_by_folder.get(model_dir, [])
                    
                    # Collect files in model directory
                    files = []
                    total_size = 0
                    for f in os.listdir(model_path):
                        fp = os.path.join(model_path, f)
                        if os.path.isfile(fp):
                            fsize = os.path.getsize(fp)
                            files.append({
                                "name": f,
                                "path": fp,
                                "size": fsize
                            })
                            total_size += fsize
                        elif os.path.isdir(fp):
                            # Subdirectory (e.g. snapshots)
                            dir_size = sum(
                                os.path.getsize(os.path.join(dp, fn))
                                for dp, _, fns in os.walk(fp)
                                for fn in fns
                            )
                            files.append({
                                "name": f,
                                "path": fp,
                                "size": dir_size,
                                "is_dir": True
                            })
                            total_size += dir_size
                    
                    model_info = {
                        "name": model_dir,
                        "path": model_path,
                        "has_best_model": any(Path(run["path"]).name == "best_model.pkl" for run in runs),
                        "created_at": os.path.getctime(model_path),
                        "files": files,
                        "file_count": len(files),
                        "total_size": total_size
                    }
                    
                    datasets = {run["dataset"] for run in runs}
                    groups = {run["synthetic"] for run in runs}
                    model_info["dataset"] = (datasets.pop() or "unknown") if len(datasets) == 1 else "unknown"
                    model_info["synthetic"] = groups.pop() if len(groups) == 1 else None
                    model_info["auc"] = runs[0]["auc"] if len(runs) == 1 else None
                    model_info["display_name"] = model_dir
                    if len(runs) == 1 and runs[0]["is_preset"]:
                        model_info["config_id"] = runs[0]["id"]
                        model_info["display_name"] = runs[0]["name"]
                    
                    log_files = []
                    for run in runs:
                        if not run["record_path"]:
                            continue
                        record = Path(run["record_path"])
                        log_files.append({
                            "name": record.name,
                            "display_name": f"{Path(run['path']).parent.name}/{record.name}",
                            "path": str(record),
                            "size": record.stat().st_size
                        })
                    model_info["log_files"] = log_files
                    model_info["log_count"] = len(log_files)
                    
                    models.append(model_info)
        
        return sorted(models, key=lambda x: x["created_at"], reverse=True)
    
    def get_synthetic_samples(self, dataset: str = 'shanghaitech') -> dict:
        """Get available synthetic samples for a dataset"""
        if dataset == 'shanghaitech':
            feature_dir = SHT_FEATURE_PATH
        else:
            feature_dir = UCF_FEATURE_PATH
        
        # Find synthetic samples in feature directory
        available_samples = []
        if os.path.exists(feature_dir):
            for f in os.listdir(feature_dir):
                if f.endswith('_0.npy'):
                    video_name = f[:-6]  # Remove _0.npy
                    if video_name.startswith('Gen'):
                        available_samples.append(video_name)
        
        available_samples = sorted(list(set(available_samples)))
        
        return {
            "dataset": dataset,
            "available_samples": available_samples,
            "default_samples": ",".join(available_samples),
            "total_available": len(available_samples)
        }
    
    def delete_model(self, model_name: str) -> dict:
        """Delete a trained model (move to recycle bin)"""
        from services.trash_service import trash_folder
        
        model_path = os.path.join(CKPT_PATH, model_name)
        
        if not os.path.exists(model_path):
            return {"success": False, "error": f"Model not found: {model_name}"}
        
        try:
            entry = trash_folder(model_path)
            if entry:
                return {"success": True, "model_name": model_name, "trash_id": entry['id']}
            return {"success": False, "error": "Failed to move to trash"}
        except Exception as e:
            return {"success": False, "error": str(e)}
