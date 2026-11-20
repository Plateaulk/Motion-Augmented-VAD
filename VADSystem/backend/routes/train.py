"""Training API Routes"""
from flask import Blueprint, request, jsonify
import os
from pathlib import Path
import math
import re

train_bp = Blueprint('train', __name__)

@train_bp.route('/start', methods=['POST'])
def start_training():
    """Start a training job"""
    from services.train_service import TrainService
    from config import DATASET_PATH, DEFAULT_SYNTHETIC_RATIOS
    
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='JSON object required'), 400
    dataset = data.get('dataset', 'shanghaitech')
    if dataset not in ('shanghaitech', 'ucf-crime'):
        return jsonify(error='Unsupported dataset'), 400
    seed = 1
    # Frontend sends iterations, backend maps to max_iters
    max_iters = data.get('iterations', data.get('max_iters', 600))
    k = data.get('k', 5)
    synthetic_ratio = data.get('synthetic_ratio', DEFAULT_SYNTHETIC_RATIOS[dataset])
    # Frontend sends exp_name, backend maps to model_name
    model_name = data.get('exp_name', data.get('model_name', None))
    # Additional params
    sample_size = data.get('sample_size', 30)
    learning_rate = data.get('learning_rate', 0.0005)
    batch_size = data.get('batch_size', 1)
    snapshot = data.get('snapshot', 1)
    if isinstance(snapshot, bool):
        snapshot = int(snapshot)
    plot = data.get('plot', 0)
    if isinstance(plot, bool):
        plot = 1 if plot else 0
    
    # Process synthetic samples: convert use_synthetic + synthetic_dir to synthetic_samples
    # Core logic: use selected dir synthetic samples + original dataset for training
    synthetic_samples = data.get('synthetic_samples', None)
    use_synthetic = data.get('use_synthetic', False)
    synthetic_dir = data.get('synthetic_dir', '')
    
    if not isinstance(synthetic_ratio, (int, float)) or not math.isfinite(synthetic_ratio) or not 0 <= synthetic_ratio <= 1:
        return jsonify(error='synthetic_ratio must be in [0, 1]'), 400
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1 or batch_size != 1:
        return jsonify(error='sample_size must be positive and batch_size must be 1'), 400
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        return jsonify(error='k must be a positive integer'), 400
    if model_name is not None and (not isinstance(model_name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', model_name)):
        return jsonify(error='Experiment name must contain only letters, digits, underscores or hyphens'), 400
    if not isinstance(use_synthetic, bool):
        return jsonify(error='use_synthetic must be true or false'), 400
    if not isinstance(max_iters, int) or isinstance(max_iters, bool) or max_iters < 1:
        return jsonify(error='iterations must be a positive integer'), 400
    if not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
        return jsonify(error='learning_rate must be positive and finite'), 400
    if not isinstance(snapshot, int) or snapshot < 0 or plot not in (0, 1):
        return jsonify(error='snapshot must be nonnegative and plot must be 0 or 1'), 400
    folder = 'SH_clip_video_features' if dataset == 'shanghaitech' else 'UCFClipFeatures'
    feature_root = (Path(DATASET_PATH) / dataset / folder).resolve()
    feature_dir = feature_root
    if use_synthetic:
        if not isinstance(synthetic_dir, str) or not synthetic_dir or Path(synthetic_dir).is_absolute():
            return jsonify(error='Select a synthetic directory relative to DATASET_PATH'), 400
        feature_dir = (Path(DATASET_PATH) / synthetic_dir).resolve()
        if not feature_dir.is_relative_to(feature_root) or not feature_dir.is_dir():
            return jsonify(error='Synthetic directory does not match the selected dataset'), 400
        if not synthetic_samples:
            ids = set()
            for path in feature_dir.glob('*.npy'):
                match = re.fullmatch(r'(.+)_([0-9])', path.stem)
                if match and (feature_dir != feature_root or path.name.startswith('Gen')):
                    ids.add(match.group(1))
            if not ids:
                return jsonify(error='No synthetic samples found in the selected directory'), 400
            synthetic_samples = ','.join(sorted(ids))
    if synthetic_samples:
        if not isinstance(synthetic_samples, str):
            return jsonify(error='synthetic_samples must be comma-separated IDs'), 400
        ids = [name.strip() for name in synthetic_samples.split(',')]
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', name) for name in ids):
            return jsonify(error='Invalid or duplicate synthetic sample IDs'), 400
        # Validate every crop and every collision before creating any root links.
        links = []
        for name in ids:
            for crop in range(10):
                source = feature_dir / f'{name}_{crop}.npy'
                target = feature_root / source.name
                if not source.is_file():
                    return jsonify(error=f'Missing synthetic crop: {source.name}'), 400
                if feature_dir != feature_root:
                    if (target.exists() or target.is_symlink()) and target.resolve() != source.resolve():
                        return jsonify(error=f'Feature name collision: {source.name}'), 409
                    if not target.exists() and not target.is_symlink():
                        links.append((source, target))
        try:
            for source, target in links:
                target.symlink_to(source)
        except OSError as error:
            return jsonify(error=f'Cannot link synthetic features: {error}'), 400

    service = TrainService()
    result = service.start_training(
        dataset=dataset,
        seed=seed,
        max_iters=max_iters,
        k=k,
        synthetic_samples=synthetic_samples,
        synthetic_ratio=synthetic_ratio,
        model_name=model_name,
        sample_size=sample_size,
        lr=learning_rate,
        batch_size=batch_size,
        snapshot=snapshot,
        plot=plot
    )
    
    return jsonify(result)

@train_bp.route('/stop', methods=['POST'])
def stop_training():
    """Stop current training job"""
    from services.train_service import TrainService
    
    service = TrainService()
    result = service.stop_training()
    
    return jsonify(result)

@train_bp.route('/status', methods=['GET'])
def get_status():
    """Get training status"""
    from services.train_service import TrainService
    
    service = TrainService()
    status = service.get_status()
    
    return jsonify(status)

@train_bp.route('/logs', methods=['GET'])
def get_logs():
    """Get training logs"""
    from services.train_service import TrainService
    
    n = request.args.get('n', 100, type=int)
    
    service = TrainService()
    logs = service.get_logs(n)
    
    return jsonify({"logs": logs})

@train_bp.route('/models', methods=['GET'])
def list_models():
    """List available trained models"""
    from services.train_service import TrainService
    
    service = TrainService()
    models = service.list_models()
    
    return jsonify({"models": models})

@train_bp.route('/synthetic_samples', methods=['GET'])
def get_synthetic_samples():
    """Get available synthetic samples"""
    from services.train_service import TrainService
    
    dataset = request.args.get('dataset', 'shanghaitech')
    
    service = TrainService()
    samples = service.get_synthetic_samples(dataset)
    
    return jsonify({"samples": samples, "dataset": dataset})


@train_bp.route('/delete_model', methods=['POST'])
def delete_model():
    """Delete a trained model (move to recycle bin)"""
    from services.train_service import TrainService
    
    data = request.json
    model_name = data.get('model_name')
    
    if not model_name:
        return jsonify({"error": "model_name is required"}), 400
    
    service = TrainService()
    result = service.delete_model(model_name)
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 404 if "not found" in result.get("error", "").lower() else 500


@train_bp.route('/rename_model', methods=['POST'])
def rename_model():
    """Rename a trained model directory"""
    from config import CKPT_PATH
    
    data = request.json
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    if not old_name or not new_name:
        return jsonify({"error": "old_name and new_name are required"}), 400
    
    old_path = os.path.join(CKPT_PATH, old_name)
    new_path = os.path.join(CKPT_PATH, new_name)
    
    if not os.path.exists(old_path):
        return jsonify({"error": f"Model not found: {old_name}"}), 404
    
    # Auto-suffix on name collision
    original_new_name = new_name
    counter = 1
    while os.path.exists(new_path):
        counter += 1
        new_name = f"{original_new_name}_{counter}"
        new_path = os.path.join(CKPT_PATH, new_name)
    
    try:
        os.rename(old_path, new_path)
        return jsonify({"success": True, "old_name": old_name, "new_name": new_name})
    except Exception as e:
        return jsonify({"error": f"Rename failed: {e}"}), 500
