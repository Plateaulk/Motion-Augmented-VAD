"""Data Processing API Routes"""
from flask import Blueprint, request, jsonify
import os
import glob
import numpy as np

data_bp = Blueprint('data', __name__)

@data_bp.route('/feature_dirs', methods=['GET'])
def list_feature_directories():
    """List all available feature directories including system folders"""
    from config import DATASET_PATH, SHT_FEATURE_SYSTEM_DIR, UCF_FEATURE_SYSTEM_DIR
    
    directories = []
    
    # Add system default folders first
    system_folders = [
        {
            "name": "shanghaitech/SH_clip_video_features/system_extracted",
            "dataset": "System Feature (SHT)",
            "folder": "system_extracted",
            "path": SHT_FEATURE_SYSTEM_DIR,
            "synthetic_count": 0,
            "total_count": 0,
            "is_system": True,
            "is_root": False
        },
        {
            "name": "ucf-crime/UCFClipFeatures/system_extracted",
            "dataset": "System Feature (UCF)",
            "folder": "system_extracted",
            "path": UCF_FEATURE_SYSTEM_DIR,
            "synthetic_count": 0,
            "total_count": 0,
            "is_system": True,
            "is_root": False
        }
    ]
    
    # Count files in system folders
    for sf in system_folders:
        if os.path.exists(sf["path"]):
            total = 0
            synthetic = 0
            for f in os.listdir(sf["path"]):
                if f.endswith('.npy'):
                    total += 1
                    if f.startswith('Gen'):
                        synthetic += 1
            sf["synthetic_count"] = synthetic // 10
            sf["total_count"] = total // 10
    
    directories.extend(system_folders)
    
    # Scan for dataset directories with feature folders
    for dataset_name in os.listdir(DATASET_PATH):
        dataset_path = os.path.join(DATASET_PATH, dataset_name)
        if not os.path.isdir(dataset_path):
            continue
        
        # Look for feature directories (root feature dirs)
        for item in os.listdir(dataset_path):
            item_path = os.path.join(dataset_path, item)
            if os.path.isdir(item_path) and ('feature' in item.lower() or 'clip' in item.lower()):
                # Count synthetic features in root dir
                synthetic_count = 0
                total_count = 0
                for f in os.listdir(item_path):
                    if f.endswith('.npy'):
                        total_count += 1
                        if f.startswith('Gen'):
                            synthetic_count += 1
                
                # Root feature directory (contains entire dataset, used by training)
                directories.append({
                    "name": f"{dataset_name}/{item}",
                    "dataset": dataset_name,
                    "folder": item,
                    "path": item_path,
                    "synthetic_count": synthetic_count // 10,
                    "total_count": total_count // 10,
                    "is_system": False,
                    "is_root": True
                })
                
                # Scan for user-created sub-directories (NOT system_extracted, already added)
                for sub in os.listdir(item_path):
                    sub_path = os.path.join(item_path, sub)
                    if os.path.isdir(sub_path) and sub != 'system_extracted':
                        sub_total = 0
                        sub_synth = 0
                        for f in os.listdir(sub_path):
                            if f.endswith('.npy'):
                                sub_total += 1
                                if f.startswith('Gen'):
                                    sub_synth += 1
                        directories.append({
                            "name": f"{dataset_name}/{item}/{sub}",
                            "dataset": dataset_name,
                            "folder": sub,
                            "path": sub_path,
                            "synthetic_count": sub_synth // 10,
                            "total_count": sub_total // 10,
                            "is_system": False,
                            "is_root": False
                })
    
    return jsonify({
        "directories": directories,
        "success": True
    })

@data_bp.route('/features', methods=['GET'])
def list_features():
    """List all feature files (.npy) for a dataset directory"""
    from config import SHT_FEATURE_PATH, UCF_FEATURE_PATH, DATASET_PATH
    
    # Support both 'dataset' (legacy) and 'directory' (new) parameters
    directory = request.args.get('directory', None)
    dataset = request.args.get('dataset', 'shanghaitech')
    
    if directory:
        # Use custom directory path
        feature_dir = os.path.join(DATASET_PATH, directory)
    elif dataset == 'ucf-crime':
        feature_dir = UCF_FEATURE_PATH
    else:
        feature_dir = SHT_FEATURE_PATH
    
    # Whether to return only synthetic samples (Gen-prefixed)
    synthetic_only = request.args.get('synthetic_only', 'false').lower() == 'true'
    
    # Group features by video name (all .npy files)
    video_features = {}
    
    if os.path.exists(feature_dir):
        for f in os.listdir(feature_dir):
            if not f.endswith('.npy'):
                continue
            # Skip non-synthetic files in synthetic_only mode
            if synthetic_only and not f.startswith('Gen'):
                continue
            
            # Extract video name (remove _X.npy suffix)
            # Format: GenSHT001_0.npy, W900445_00001__0.npy, test_0.npy etc.
            parts = f.rsplit('_', 1)
            if len(parts) == 2 and parts[1].replace('.npy', '').isdigit():
                video_name = parts[0]
            else:
                video_name = f.replace('.npy', '')
            
            if video_name not in video_features:
                video_features[video_name] = {
                    'name': video_name,
                    'files': [],
                    'total_size': 0
                }
            
            feature_path = os.path.join(feature_dir, f)
            video_features[video_name]['files'].append(f)
            try:
                video_features[video_name]['total_size'] += os.path.getsize(feature_path)
            except:
                pass
    
    # Convert to list (skip numpy data, stats only for speed)
    features = []
    for video_name, info in video_features.items():
        first_file = sorted(info['files'])[0]
        feature_path = os.path.join(feature_dir, first_file)
        
        is_synthetic = video_name.startswith('Gen')
        
        features.append({
            'name': video_name,
            'crop_count': len(info['files']),
            'total_size': info['total_size'],
            'is_synthetic': is_synthetic,
            'path': feature_path
        })
    
    # Sort by name
    features.sort(key=lambda x: x['name'])
    
    return jsonify({
        "features": features,
        "total": len(features),
        "dataset": dataset
    })


@data_bp.route('/feature_info', methods=['GET'])
def get_feature_info():
    """Get detailed info about a specific feature file"""
    from config import SHT_FEATURE_PATH, UCF_FEATURE_PATH
    
    video_name = request.args.get('video_name')
    dataset = request.args.get('dataset', 'shanghaitech')
    
    if not video_name:
        return jsonify({"error": "video_name is required"}), 400
    
    if dataset == 'ucf-crime':
        feature_dir = UCF_FEATURE_PATH
    else:
        feature_dir = SHT_FEATURE_PATH
    
    feature_path = os.path.join(feature_dir, f"{video_name}_0.npy")
    
    if not os.path.exists(feature_path):
        return jsonify({"error": "Feature file not found", "exists": False})
    
    try:
        data = np.load(feature_path)
        return jsonify({
            "exists": True,
            "path": feature_path,
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "size_bytes": os.path.getsize(feature_path)
        })
    except Exception as e:
        return jsonify({"error": str(e), "exists": True})


@data_bp.route('/delete_feature', methods=['POST'])
def delete_feature():
    """Delete a feature file (moves to recycle bin)"""
    from config import SHT_FEATURE_PATH, UCF_FEATURE_PATH, DATASET_PATH
    from services.trash_service import trash_file
    
    data = request.json
    video_name = data.get('video_name')
    dataset = data.get('dataset', 'shanghaitech')
    directory = data.get('directory', None)
    
    if not video_name:
        return jsonify({"error": "video_name is required"}), 400
    
    if directory:
        feature_dir = os.path.join(DATASET_PATH, directory)
    elif dataset == 'ucf-crime':
        feature_dir = UCF_FEATURE_PATH
    else:
        feature_dir = SHT_FEATURE_PATH
    
    deleted = []
    # Delete all crop files (_0.npy to _9.npy)
    for i in range(10):
        feature_path = os.path.join(feature_dir, f"{video_name}_{i}.npy")
        if os.path.exists(feature_path):
            try:
                entry = trash_file(feature_path)
                if entry:
                    deleted.append(f"{video_name}_{i}.npy")
            except Exception as e:
                return jsonify({"error": f"Failed to delete {feature_path}: {e}"}), 500
    
    if deleted:
        return jsonify({"success": True, "deleted": deleted})
    else:
        return jsonify({"error": "No feature files found for this video"}), 404


@data_bp.route('/copy_features', methods=['POST'])
def copy_features():
    """Copy feature files to another directory"""
    from config import DATASET_PATH
    import shutil
    
    data = request.json
    features = data.get('features', [])
    source_dir = data.get('source_dir')
    target_dir = data.get('target_dir')
    
    if not features or not source_dir or not target_dir:
        return jsonify({"error": "features, source_dir, and target_dir are required"}), 400
    
    source_path = os.path.join(DATASET_PATH, source_dir)
    target_path = os.path.join(DATASET_PATH, target_dir)
    
    if not os.path.exists(source_path):
        return jsonify({"error": f"Source directory not found: {source_dir}"}), 404
    
    os.makedirs(target_path, exist_ok=True)
    
    copied = []
    errors = []
    
    for feature_name in features:
        # Check for name collision, add suffix if needed
        actual_name = feature_name
        if os.path.exists(os.path.join(target_path, f"{actual_name}_0.npy")):
            counter = 1
            while True:
                counter += 1
                actual_name = f"{feature_name}_{counter}"
                if not os.path.exists(os.path.join(target_path, f"{actual_name}_0.npy")):
                    break
        
        # Copy all crop files
        for i in range(10):
            src_file = os.path.join(source_path, f"{feature_name}_{i}.npy")
            dst_file = os.path.join(target_path, f"{actual_name}_{i}.npy")
            
            if os.path.exists(src_file):
                try:
                    shutil.copy2(src_file, dst_file)
                    copied.append(f"{actual_name}_{i}.npy")
                except Exception as e:
                    errors.append(f"{feature_name}_{i}: {str(e)}")
    
    return jsonify({
        "success": True,
        "copied": len(set(f.rsplit('_', 1)[0] for f in copied)),
        "copied_files": copied,
        "errors": errors
    })


@data_bp.route('/move_features', methods=['POST'])
def move_features():
    """Move feature files to another directory"""
    from config import DATASET_PATH
    import shutil
    
    data = request.json
    features = data.get('features', [])
    source_dir = data.get('source_dir')
    target_dir = data.get('target_dir')
    
    if not features or not source_dir or not target_dir:
        return jsonify({"error": "features, source_dir, and target_dir are required"}), 400
    
    source_path = os.path.join(DATASET_PATH, source_dir)
    target_path = os.path.join(DATASET_PATH, target_dir)
    
    if not os.path.exists(source_path):
        return jsonify({"error": f"Source directory not found: {source_dir}"}), 404
    
    os.makedirs(target_path, exist_ok=True)
    
    moved = []
    errors = []
    
    for feature_name in features:
        # Check for name collision, add suffix if needed
        actual_name = feature_name
        if os.path.exists(os.path.join(target_path, f"{actual_name}_0.npy")):
            counter = 1
            while True:
                counter += 1
                actual_name = f"{feature_name}_{counter}"
                if not os.path.exists(os.path.join(target_path, f"{actual_name}_0.npy")):
                    break
        
        # Move all crop files
        for i in range(10):
            src_file = os.path.join(source_path, f"{feature_name}_{i}.npy")
            dst_file = os.path.join(target_path, f"{actual_name}_{i}.npy")
            
            if os.path.exists(src_file):
                try:
                    shutil.move(src_file, dst_file)
                    moved.append(f"{actual_name}_{i}.npy")
                except Exception as e:
                    errors.append(f"{feature_name}_{i}: {str(e)}")
    
    return jsonify({
        "success": True,
        "moved": len(set(f.rsplit('_', 1)[0] for f in moved)),
        "moved_files": moved,
        "errors": errors
    })
