"""Feature extraction using the same implementation as the CLI."""
import importlib.util
import os
from pathlib import Path
from typing import List

import numpy as np
import torch

from config import REPO_ROOT, SHT_FEATURE_PATH, UCF_FEATURE_PATH

_spec = importlib.util.spec_from_file_location(
    "vad_feature_extractor", Path(REPO_ROOT) / "ProDisc-VAD" / "extract_features.py"
)
extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extractor)


def feature_directory(dataset):
    extractor.get_protocol(dataset)
    return SHT_FEATURE_PATH if dataset == "shanghaitech" else UCF_FEATURE_PATH


class FeatureService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.preprocess = None
        self.model_dataset = None

    def _load_model(self, dataset):
        if self.model_dataset != dataset:
            self.model, self.preprocess = extractor.load_clip_encoder(dataset, self.device)
            self.model_dataset = dataset

    def extract_features(self, video_path, video_name=None, dataset="shanghaitech", output_dir=None, save=True):
        source = extractor.validate_source(video_path, dataset)
        video_name = video_name if video_name is not None else source.stem
        output_dir = output_dir if output_dir is not None else feature_directory(dataset)
        if save:
            extractor.feature_targets(output_dir, video_name)
        self._load_model(dataset)
        result = extractor.extract_clip_features(source, self.model, self.preprocess, self.device, dataset)
        features = result.pop("features")
        result.update(success=True, video_name=video_name, video_path=str(source), saved=save)
        if save:
            paths = extractor.save_features(features, output_dir, video_name)
            result.update(feature_path=str(paths[0]), feature_dir=str(output_dir))
        else:
            result["features"] = features.tolist()
        return result

    def extract_features_batch(
        self,
        video_paths: List[str],
        dataset: str = 'shanghaitech'
    ) -> dict:
        """Extract features from multiple videos"""
        results = []
        for video_path in video_paths:
            result = self.extract_features(video_path, dataset=dataset)
            results.append(result)
        
        return {
            "success": True,
            "total": len(video_paths),
            "completed": len([r for r in results if r.get("success")]),
            "results": results
        }
    
    def get_feature_info(self, video_name: str, dataset: str = 'shanghaitech') -> dict:
        """Get information about existing features"""
        feature_dir = feature_directory(dataset)
        
        feature_path = os.path.join(feature_dir, f"{video_name}_0.npy")
        
        if not os.path.exists(feature_path):
            return {"exists": False, "video_name": video_name}
        
        try:
            features = np.load(feature_path, allow_pickle=False)
            return {
                "exists": True,
                "video_name": video_name,
                "feature_path": feature_path,
                "shape": list(features.shape),
                "dtype": str(features.dtype)
            }
        except Exception as e:
            return {"exists": True, "video_name": video_name, "error": str(e)}
    
    def list_features(self, dataset: str = 'shanghaitech') -> List[str]:
        """List all videos with extracted features"""
        feature_dir = feature_directory(dataset)
        
        videos = set()
        if os.path.exists(feature_dir):
            for f in os.listdir(feature_dir):
                if f.endswith('.npy'):
                    # Remove _X.npy suffix
                    video_name = '_'.join(f.split('_')[:-1])
                    if video_name:
                        videos.add(video_name)
        
        return sorted(list(videos))
