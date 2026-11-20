"""Inference API Routes"""
from flask import Blueprint, request, jsonify
import os
from pathlib import Path
import re

infer_bp = Blueprint('infer', __name__)

@infer_bp.route('/models', methods=['GET'])
def list_models():
    """List available inference models"""
    from services.infer_service import InferService
    
    service = InferService()
    models = service.list_models()
    
    return jsonify({"models": models})

@infer_bp.route('/extract', methods=['POST'])
def extract_features():
    """Extract with an explicit dataset and a matching destination."""
    from config import DATASET_PATH, SHT_FEATURE_PATH, UCF_FEATURE_PATH, VIDEO_OUTPUT_DIR, UPLOAD_DIR

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object required"), 400
    dataset = data.get("dataset")
    roots = {"shanghaitech": SHT_FEATURE_PATH, "ucf-crime": UCF_FEATURE_PATH}
    if not isinstance(dataset, str) or dataset not in roots:
        return jsonify(error="dataset must be shanghaitech or ucf-crime"), 400
    video_path, video_name = data.get("video_path"), data.get("video_name")
    if not isinstance(video_path, str) or not video_path:
        return jsonify(error="video_path is required"), 400
    if not isinstance(video_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", video_name):
        return jsonify(error="Feature name must contain 1-128 letters, digits, underscores or hyphens"), 400
    source = Path(video_path).resolve()
    if not any(source.is_relative_to(Path(p).resolve()) for p in (VIDEO_OUTPUT_DIR, UPLOAD_DIR, DATASET_PATH)):
        return jsonify(error="Source must be under configured video, upload or dataset directories"), 400
    target_dir = data.get("target_dir")
    if target_dir is not None and (not isinstance(target_dir, str) or not target_dir):
        return jsonify(error="target_dir must be a nonempty relative directory"), 400
    feature_root = Path(roots[dataset]).resolve()
    output_dir = (Path(DATASET_PATH) / target_dir).resolve() if target_dir else feature_root
    if target_dir and Path(target_dir).is_absolute():
        return jsonify(error="target_dir must be relative to DATASET_PATH"), 400
    if not output_dir.is_relative_to(feature_root):
        return jsonify(error="Output directory does not match the selected dataset"), 400
    try:
        from services.feature_service import FeatureService
        result = FeatureService().extract_features(str(source), video_name, dataset, str(output_dir))
    except FileExistsError as error:
        return jsonify(error=str(error)), 409
    except FileNotFoundError as error:
        return jsonify(error=str(error)), 404
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(result)

@infer_bp.route('/predict', methods=['POST'])
def predict():
    """Run inference on video"""
    from services.infer_service import InferService
    
    data = request.json
    video_name = data.get('video_name')
    model_id = data.get('model_id')
    feature_path = data.get('feature_path', None)
    
    if not video_name or not model_id:
        return jsonify({"error": "video_name and model_id are required"}), 400
    
    service = InferService()
    result = service.predict(video_name, model_id, feature_path)
    
    return jsonify(result)

@infer_bp.route('/predict_batch', methods=['POST'])
def predict_batch():
    """Run batch inference. Accepts video_names list or dataset to auto-load test videos."""
    from services.infer_service import InferService
    
    data = request.json
    video_names = data.get('video_names', [])
    model_id = data.get('model_id')
    dataset = data.get('dataset', None)
    
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    
    service = InferService()
    
    # If no video_names but dataset specified, auto-load test videos
    if not video_names and dataset:
        video_names = service.list_videos(dataset)
        if not video_names:
            return jsonify({"error": f"No test videos found for dataset: {dataset}"}), 404
    
    if not video_names:
        return jsonify({"error": "video_names or dataset is required"}), 400
    
    result = service.predict_batch(video_names, model_id)
    
    return jsonify(result)

@infer_bp.route('/compare', methods=['POST'])
def compare_models():
    """Compare predictions from multiple models"""
    from services.infer_service import InferService
    
    data = request.json
    video_name = data.get('video_name')
    model_ids = data.get('model_ids', [])
    
    if not video_name or not model_ids:
        return jsonify({"error": "video_name and model_ids are required"}), 400
    
    service = InferService()
    result = service.compare_models(video_name, model_ids)
    
    return jsonify(result)

@infer_bp.route('/videos', methods=['GET'])
def list_videos():
    """List videos available for inference"""
    from services.infer_service import InferService
    
    dataset = request.args.get('dataset', 'shanghaitech')
    
    service = InferService()
    try:
        videos = service.list_videos(dataset)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    return jsonify({"videos": videos, "dataset": dataset})
