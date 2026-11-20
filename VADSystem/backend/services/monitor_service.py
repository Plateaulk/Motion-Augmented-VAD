"""Score a representative camera frame with the selected dataset's ten-crop pipeline."""
import base64
import binascii
import threading

import cv2
import numpy as np

from services.analysis_service import find_model_run, model_runs
from services.feature_service import FeatureService, extractor
from services.infer_service import InferService


class MonitorManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._infer_service = InferService()
        self._encoder = FeatureService()
        self._lock = threading.Lock()
        self._scores = []
        self.active = False
        self.model_id = ""
        self._model = None

    def _prepare(self, model_id):
        run = find_model_run(model_runs(), model_id)
        if not run or not run["available"]:
            raise ValueError(f"Checkpoint unavailable: {model_id}")
        model = self._infer_service._load_model(model_id, run)
        if model is None:
            raise ValueError(f"Cannot load model: {model_id}")
        self._encoder._load_model(run["dataset"])
        return model

    def preload(self, model_id):
        with self._lock:
            if self.active and model_id != self.model_id:
                return {"success": False, "error": "Stop the current monitor before switching models"}
            try:
                self._prepare(model_id)
            except Exception as error:
                return {"success": False, "error": str(error)}
            return {"success": True, "model_id": model_id, "clip_ready": True,
                    "model_ready": True, "active": self.active}

    def start(self, model_id, threshold=0.5):
        with self._lock:
            try:
                self._model = self._prepare(model_id)
            except Exception as error:
                return {"success": False, "error": str(error)}
            self.model_id = model_id
            self._scores = []
            self.active = True
            return {"success": True, "model_id": model_id}

    def stop(self):
        with self._lock:
            self.active = False
            self._scores = []
            return {"success": True}

    def status(self):
        with self._lock:
            return {"active": self.active, "model_id": self.model_id, "clip_ready": self._encoder.model is not None,
                    "total_segments": len(self._scores), "total_scores": len(self._scores), "scores": list(self._scores)}

    def analyze_frame(self, frame_b64, model_id, threshold):
        with self._lock:
            if not self.active or self.model_id != model_id:
                return {"success": False, "error": "Start monitoring with the selected model first"}
            try:
                data = base64.b64decode(frame_b64.split(",", 1)[-1], validate=True)
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("Cannot decode camera frame")
                encoder = self._encoder
                crops = extractor.encode_frame_crops(frame, encoder.model, encoder.preprocess,
                                                     encoder.device, encoder.model_dataset)
                # ProDisc-VAD scores each time step independently in evaluation mode.
                scores, _, _ = self._infer_service._predict_feature_batch(self._model, crops[:, None, :])
            except (ValueError, binascii.Error, cv2.error) as error:
                return {"success": False, "error": str(error)}

            score = float(scores[0])
            self._scores.append(score)
            n = len(self._scores)
            return {"success": True, "score": score, "scores": list(self._scores), "alert": score > threshold,
                    "segment_index": n - 1, "total_segments": n, "total_scores": n}
