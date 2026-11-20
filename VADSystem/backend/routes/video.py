"""Video Generation API Routes"""
from flask import Blueprint, abort, make_response, request, jsonify, send_file
import os

video_bp = Blueprint('video', __name__)


def _unique_path(target_path):
    """If target_path exists, auto-add _2, _3... suffix to avoid collision."""
    if not os.path.exists(target_path):
        return target_path
    base, ext = os.path.splitext(target_path)
    # Folders have no extension
    if os.path.isdir(target_path) or not ext:
        base = target_path
        ext = ''
    counter = 1
    while True:
        counter += 1
        new_path = f"{base}_{counter}{ext}"
        if not os.path.exists(new_path):
            return new_path

@video_bp.route('/backgrounds', methods=['GET'])
def get_backgrounds():
    """Get list of available background images"""
    from services.comfyui_service import ComfyUIService
    
    dataset = request.args.get('dataset', '')  # Optional: specify dataset, empty returns all
    folder = request.args.get('folder', '')  # Optional: specify subfolder
    search = request.args.get('search', '')  # Optional: search keyword
    
    service = ComfyUIService()
    
    # If no dataset, return all backgrounds
    if not dataset or dataset == 'all':
        all_backgrounds = []
        for ds in ['sht', 'ucf', 'system']:
            bgs = service.get_backgrounds(ds, folder, search)
            all_backgrounds.extend(bgs)
        return jsonify({"backgrounds": all_backgrounds, "dataset": "all"})
    
    backgrounds = service.get_backgrounds(dataset, folder, search)
    return jsonify({"backgrounds": backgrounds, "dataset": dataset})


@video_bp.route('/background_folders', methods=['GET'])
def get_background_folders():
    """Get list of background folders"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR
    
    dataset = request.args.get('dataset', 'sht')
    bg_dir = UCF_BACKGROUND_DIR if dataset == 'ucf' else SHT_BACKGROUND_DIR
    
    folders = [{'name': 'All', 'path': ''}]  # Default option
    
    if os.path.exists(bg_dir):
        for item in sorted(os.listdir(bg_dir)):
            item_path = os.path.join(bg_dir, item)
            if os.path.isdir(item_path):
                # Count images in folder
                count = len([f for f in os.listdir(item_path) 
                           if f.lower().endswith(('.jpg', '.png', '.jpeg', '.webp'))])
                folders.append({
                    'name': item,
                    'path': item,
                    'count': count
                })
    
    return jsonify({"folders": folders, "dataset": dataset})

def _align_to_16(val):
    """Align resolution value to nearest multiple of 16 (required by WAN model)"""
    return max(16, round(val / 16) * 16)


def _duration_seconds(data):
    if 'duration_seconds' not in data:
        return None
    seconds = data['duration_seconds']
    if type(seconds) not in (int, float) or not 1 <= seconds <= 10:
        abort(make_response(jsonify(error="Duration must be between 1 and 10 seconds"), 400))
    return seconds


@video_bp.route('/t2v', methods=['POST'])
def text_to_video():
    """Generate video from text"""
    from services.comfyui_service import ComfyUIService
    
    data = request.json
    prompt = data.get('prompt', '')
    negative_prompt = data.get('negative_prompt', '')
    width = _align_to_16(data.get('width', 848))
    height = _align_to_16(data.get('height', 480))
    length = data.get('length', 81)
    seed = 1
    output_name = data.get('output_name', None)
    output_folder = data.get('output_folder', None)
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    
    service = ComfyUIService()
    result = service.text_to_video(prompt, negative_prompt, width, height, length, seed, output_name, output_folder,
                                   duration_seconds=_duration_seconds(data))
    
    return jsonify(result)

@video_bp.route('/i2v', methods=['POST'])
def image_to_video():
    """Generate video from image"""
    from services.comfyui_service import ComfyUIService
    
    data = request.json
    prompt = data.get('prompt', '')
    negative_prompt = data.get('negative_prompt', '')
    background = data.get('background')
    dataset = data.get('dataset', 'sht')
    width = _align_to_16(data.get('width', 848))
    height = _align_to_16(data.get('height', 480))
    length = data.get('length', 81)
    seed = 1
    output_name = data.get('output_name', None)
    output_folder = data.get('output_folder', None)
    
    if not prompt or not background:
        return jsonify({"error": "Prompt and background are required"}), 400
    
    service = ComfyUIService()
    result = service.image_to_video(
        prompt, negative_prompt, background, dataset,
        width, height, length, seed, output_name, output_folder, duration_seconds=_duration_seconds(data)
    )
    
    return jsonify(result)

@video_bp.route('/v2v', methods=['POST'])
def video_to_video():
    """Generate video from video (using mask)"""
    from services.comfyui_service import ComfyUIService
    
    data = request.json
    prompt = data.get('prompt', '')
    negative_prompt = data.get('negative_prompt', '')
    motion_id = data.get('motion_id')
    render_id = data.get('render_id')  # Specific render to use
    background = data.get('background')
    dataset = data.get('dataset', 'sht')
    width = _align_to_16(data.get('width', 848))
    height = _align_to_16(data.get('height', 480))
    length = data.get('length', 81)
    seed = 1
    output_name = data.get('output_name', None)
    output_folder = data.get('output_folder', None)
    
    if not prompt or not motion_id:
        return jsonify({"error": "Prompt and motion_id are required"}), 400
    
    service = ComfyUIService()
    result = service.video_to_video(
        prompt, negative_prompt, motion_id, background, dataset,
        width, height, length, seed, output_name, render_id, output_folder,
        duration_seconds=_duration_seconds(data), motion_directory=data.get('motion_directory')
    )
    
    return jsonify(result)

@video_bp.route('/status/<job_id>', methods=['GET'])
def get_video_status(job_id):
    """Get status of video generation job"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    status = service.get_job_status(job_id)
    
    return jsonify(status)

@video_bp.route('/progress/<prompt_id>', methods=['GET'])
def get_job_progress(prompt_id):
    """Get progress of video generation job by prompt_id"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    progress = service.get_job_progress(prompt_id)
    
    return jsonify(progress)

@video_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """Get ComfyUI queue status"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    status = service.get_queue_status()
    
    return jsonify(status)

@video_bp.route('/check_name', methods=['GET'])
def check_name():
    """Check if a name already exists in a target folder/context"""
    import re
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import COMFYUI_PATH, MOTIONSTREAMER_PATH, DATASET_PATH, SHT_FEATURE_PATH
    
    name = request.args.get('name', '').strip()
    folder = request.args.get('folder', 'system_generated')
    context = request.args.get('context', 'video')  # video, motion, feature
    
    if not name:
        return jsonify({"exists": False})
    
    if context == 'video':
        video_dir = os.path.join(COMFYUI_PATH, "output", "video", folder)
        if os.path.isdir(video_dir):
            for f in os.listdir(video_dir):
                base = os.path.splitext(f)[0]
                # Exact match, or ComfyUI suffix pattern: name_00001_ etc
                if base == name or re.match(rf'^{re.escape(name)}_\d{{5}}_?$', base):
                    return jsonify({"exists": True, "existing_file": f})
        return jsonify({"exists": False})
    
    elif context == 'motion':
        motion_dir = request.args.get('directory', '')
        if motion_dir:
            motion_path = os.path.join(MOTIONSTREAMER_PATH, motion_dir, name)
        else:
            motion_path = os.path.join(MOTIONSTREAMER_PATH, 'runs_vad_system', name)
        return jsonify({"exists": os.path.exists(motion_path)})
    
    elif context == 'feature':
        feature_dir_name = request.args.get('directory', '')
        if feature_dir_name:
            feat_path = os.path.join(DATASET_PATH, feature_dir_name)
        else:
            feat_path = SHT_FEATURE_PATH
        from services.feature_service import extractor
        try:
            extractor.feature_targets(feat_path, name)
        except FileExistsError:
            return jsonify({"exists": True, "existing_file": name})
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify({"exists": False})
    
    return jsonify({"exists": False})


@video_bp.route('/list', methods=['GET'])
def list_videos():
    """List generated videos with optional folder filter and search"""
    from services.comfyui_service import ComfyUIService
    
    folder = request.args.get('folder', '')
    search = request.args.get('search', '')
    
    service = ComfyUIService()
    videos = service.list_videos(folder, search)
    
    return jsonify({"videos": videos})


@video_bp.route('/video_folders', methods=['GET'])
def get_video_folders():
    """Get list of video folders in ComfyUI output"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    folders = service.list_video_folders()
    
    return jsonify({"folders": folders})


@video_bp.route('/file/<path:filename>', methods=['GET'])
def get_video_file(filename):
    """Serve video file from ComfyUI output"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import COMFYUI_PATH
    
    video_dir = os.path.join(COMFYUI_PATH, "output", "video")
    
    # filename can be "folder/video.mp4" or just "video.mp4"
    file_path = os.path.join(video_dir, filename)
    
    # Security check
    real_path = os.path.realpath(file_path)
    real_video_dir = os.path.realpath(video_dir)
    if not real_path.startswith(real_video_dir):
        return jsonify({"error": "Invalid path"}), 403
    
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='video/mp4')
    
    return jsonify({"error": "Video not found"}), 404


@video_bp.route('/file_thumb/<path:filename>', methods=['GET'])
def get_video_thumbnail(filename):
    """Serve video thumbnail (first frame, cached)"""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import cv2
    from config import COMFYUI_PATH

    video_dir = (Path(COMFYUI_PATH) / "output" / "video").resolve()
    file_path = (video_dir / filename).resolve()
    if not file_path.is_relative_to(video_dir):
        return jsonify({"error": "Invalid path"}), 403
    if not file_path.is_file():
        return jsonify({"error": "Video not found"}), 404

    relative = file_path.relative_to(video_dir)
    cache_path = video_dir / ".thumbs" / relative.parent / (relative.name + ".jpg")
    if cache_path.is_file():
        cached = cache_path.stat()
        if cached.st_size and cached.st_mtime_ns >= file_path.stat().st_mtime_ns:
            return send_file_with_cache(cache_path, "image/jpeg")

    capture = cv2.VideoCapture(str(file_path))
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        return jsonify({"error": "Could not decode the first video frame"}), 422

    height, width = frame.shape[:2]
    thumbnail = cv2.resize(frame, (200, max(1, round(height * 200 / width))),
                           interpolation=cv2.INTER_AREA)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=cache_path.parent) as tmp:
        jpeg = Path(tmp) / "frame.jpg"
        if not cv2.imwrite(str(jpeg), thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85]):
            return jsonify({"error": "Could not encode video thumbnail"}), 500
        os.replace(jpeg, cache_path)
    return send_file_with_cache(cache_path, "image/jpeg")


@video_bp.route('/comfyui/status', methods=['GET'])
def comfyui_status():
    """Get ComfyUI server status"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    status = service.get_server_status()
    
    return jsonify(status)

@video_bp.route('/comfyui/start', methods=['POST'])
def start_comfyui():
    """Start ComfyUI server"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    result = service.start_server()
    
    return jsonify(result)

@video_bp.route('/comfyui/stop', methods=['POST'])
def stop_comfyui():
    """Stop ComfyUI server"""
    from services.comfyui_service import ComfyUIService
    
    service = ComfyUIService()
    result = service.stop_server()
    
    return jsonify(result)

@video_bp.route('/background/<dataset>/<path:filename>', methods=['GET'])
def get_background_image(dataset, filename):
    """Serve background image file (supports subfolder paths)"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR
    
    if dataset == 'sht':
        bg_dir = SHT_BACKGROUND_DIR
    else:
        bg_dir = UCF_BACKGROUND_DIR
    
    # Support subfolder paths like "folder/image.jpg"
    file_path = os.path.join(bg_dir, filename)
    
    # Security check: ensure path is within bg_dir
    real_path = os.path.realpath(file_path)
    real_bg_dir = os.path.realpath(bg_dir)
    if not real_path.startswith(real_bg_dir):
        return jsonify({"error": "Invalid path"}), 403
    
    if os.path.exists(file_path):
        # Determine mimetype based on extension
        ext = os.path.splitext(filename)[1].lower()
        mimetypes = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
        mimetype = mimetypes.get(ext, 'image/jpeg')
        return send_file(file_path, mimetype=mimetype)
    
    return jsonify({"error": "Image not found"}), 404


def send_file_with_cache(file_path, mimetype, max_age=86400):
    """Send file with cache headers (default 24 hours)"""
    from flask import make_response
    response = make_response(send_file(file_path, mimetype=mimetype))
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    return response


@video_bp.route('/background_thumb/<dataset>/<path:filename>', methods=['GET'])
def get_background_thumbnail(dataset, filename):
    """Serve background image thumbnail (max 200px, cached)"""
    import sys
    from io import BytesIO
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR
    
    if dataset == 'sht':
        bg_dir = SHT_BACKGROUND_DIR
    else:
        bg_dir = UCF_BACKGROUND_DIR
    
    file_path = os.path.join(bg_dir, filename)
    
    # Security check
    real_path = os.path.realpath(file_path)
    real_bg_dir = os.path.realpath(bg_dir)
    if not real_path.startswith(real_bg_dir):
        return jsonify({"error": "Invalid path"}), 403
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Image not found"}), 404
    
    # Check for cached thumbnail
    cache_dir = os.path.join(bg_dir, '.thumbs')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Create cache filename (preserve subfolder structure)
    cache_filename = filename.replace('/', '_').replace('\\', '_') + '.jpg'
    cache_path = os.path.join(cache_dir, cache_filename)
    
    # Use cached if exists and newer than original
    if os.path.exists(cache_path):
        if os.path.getmtime(cache_path) >= os.path.getmtime(file_path):
            return send_file_with_cache(cache_path, 'image/jpeg')
    
    # Generate thumbnail
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize to max 200px width, maintain aspect ratio
            max_width = 200
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save to cache
            img.save(cache_path, 'JPEG', quality=75, optimize=True)
            
            # Return the thumbnail with cache headers
            return send_file_with_cache(cache_path, 'image/jpeg')
    except Exception as e:
        # Fallback to original
        return send_file(file_path, mimetype='image/jpeg')


@video_bp.route('/delete_background', methods=['POST'])
def delete_background():
    """Delete a background image (moves to recycle bin)"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR, SYSTEM_BACKGROUND_DIR
    from services.trash_service import trash_file
    
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({"error": "name is required"}), 400
    
    deleted = False
    
    for bg_dir in [SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR, SYSTEM_BACKGROUND_DIR]:
        file_path = os.path.join(bg_dir, name)
        if os.path.exists(file_path):
            try:
                entry = trash_file(file_path)
                if entry:
                    deleted = True
            except Exception as e:
                return jsonify({"error": f"Failed to delete: {e}"}), 500
    
    if deleted:
        return jsonify({"success": True, "deleted": name})
    else:
        return jsonify({"error": "Background not found"}), 404


@video_bp.route('/copy_background', methods=['POST'])
def copy_background():
    """Copy a background image to target dataset directory"""
    import sys
    import shutil
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR
    
    data = request.json
    name = data.get('name')
    target_dataset = data.get('target_dataset')  # 'sht' or 'ucf'
    
    if not name or not target_dataset:
        return jsonify({"error": "name and target_dataset are required"}), 400
    
    # Determine target directory
    target_dir = SHT_BACKGROUND_DIR if target_dataset == 'sht' else UCF_BACKGROUND_DIR
    
    # Find source file
    source_path = None
    for bg_dir in [SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR]:
        file_path = os.path.join(bg_dir, name)
        if os.path.exists(file_path):
            source_path = file_path
            break
    
    if not source_path:
        return jsonify({"error": f"Background not found: {name}"}), 404
    
    target_path = os.path.join(target_dir, name)
    
    # Check if already exists in target
    if source_path == target_path:
        return jsonify({"error": "Source and target are the same"}), 400
    
    try:
        os.makedirs(target_dir, exist_ok=True)
        target_path = _unique_path(target_path)
        shutil.copy2(source_path, target_path)
        return jsonify({"success": True, "copied": os.path.basename(target_path), "target": target_path})
    except Exception as e:
        return jsonify({"error": f"Failed to copy: {e}"}), 500


@video_bp.route('/move_background', methods=['POST'])
def move_background():
    """Move a background image to target dataset directory"""
    import sys
    import shutil
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR
    
    data = request.json
    name = data.get('name')
    target_dataset = data.get('target_dataset')  # 'sht' or 'ucf'
    
    if not name or not target_dataset:
        return jsonify({"error": "name and target_dataset are required"}), 400
    
    # Determine target directory
    target_dir = SHT_BACKGROUND_DIR if target_dataset == 'sht' else UCF_BACKGROUND_DIR
    
    # Find source file
    source_path = None
    for bg_dir in [SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR]:
        file_path = os.path.join(bg_dir, name)
        if os.path.exists(file_path):
            source_path = file_path
            break
    
    if not source_path:
        return jsonify({"error": f"Background not found: {name}"}), 404
    
    target_path = os.path.join(target_dir, name)
    
    # Check if already in target
    if source_path == target_path:
        return jsonify({"error": "File already in target directory"}), 400
    
    try:
        os.makedirs(target_dir, exist_ok=True)
        target_path = _unique_path(target_path)
        shutil.move(source_path, target_path)
        return jsonify({"success": True, "moved": os.path.basename(target_path), "target": target_path})
    except Exception as e:
        return jsonify({"error": f"Failed to move: {e}"}), 500


@video_bp.route('/copy', methods=['POST'])
def copy_video():
    """Copy a file or directory to target directory"""
    import shutil
    
    data = request.json
    source = data.get('source')
    target_dir = data.get('target_dir')
    
    if not source or not target_dir:
        return jsonify({"error": "source and target_dir are required"}), 400
    
    if not os.path.exists(source):
        return jsonify({"error": f"Source not found: {source}"}), 404
    
    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        name = os.path.basename(source)
        target_path = _unique_path(os.path.join(target_dir, name))
        if os.path.isdir(source):
            shutil.copytree(source, target_path)
        else:
            shutil.copy2(source, target_path)
        return jsonify({"success": True, "copied": os.path.basename(target_path), "target": target_path})
    except Exception as e:
        return jsonify({"error": f"Failed to copy: {e}"}), 500


@video_bp.route('/move', methods=['POST'])
def move_video():
    """Move a file or directory to target directory"""
    import shutil
    
    data = request.json
    source = data.get('source')
    target_dir = data.get('target_dir')
    
    if not source or not target_dir:
        return jsonify({"error": "source and target_dir are required"}), 400
    
    if not os.path.exists(source):
        return jsonify({"error": f"Source not found: {source}"}), 404
    
    # Prevent moving to same directory
    source_parent = os.path.dirname(os.path.abspath(source))
    if os.path.abspath(target_dir) == source_parent:
        return jsonify({"error": "Source file already in target folder"}), 400
    
    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        name = os.path.basename(source)
        target_path = _unique_path(os.path.join(target_dir, name))
        shutil.move(source, target_path)
        return jsonify({"success": True, "moved": os.path.basename(target_path), "target": target_path})
    except Exception as e:
        return jsonify({"error": f"Failed to move: {e}"}), 500


@video_bp.route('/delete', methods=['POST'])
def delete_video():
    """Delete a video file (moves to recycle bin)"""
    from services.trash_service import trash_file
    data = request.json
    path = data.get('path')
    
    if not path:
        return jsonify({"error": "path is required"}), 400
    
    if not os.path.exists(path):
        return jsonify({"error": f"File not found: {path}"}), 404
    
    try:
        entry = trash_file(path)
        if entry:
            return jsonify({"success": True, "deleted": path, "trash_id": entry["id"]})
        return jsonify({"error": "Failed to move to trash"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to delete: {e}"}), 500


@video_bp.route('/rename_file', methods=['POST'])
def rename_file():
    """Rename a file (background, video, etc.)"""
    data = request.json
    old_path = data.get('path')
    new_name = data.get('new_name')
    
    if not old_path or not new_name:
        return jsonify({"error": "path and new_name are required"}), 400
    
    if not os.path.exists(old_path):
        return jsonify({"error": f"File not found: {old_path}"}), 404
    
    # Sanitize new name - keep extension
    import re
    base_name, ext = os.path.splitext(new_name)
    old_ext = os.path.splitext(old_path)[1]
    if not ext:
        ext = old_ext  # Keep original extension if not provided
    
    # Allow alphanumeric, Chinese, underscores, hyphens, dots
    if not re.match(r'^[\w\u4e00-\u9fff\-. ]+$', base_name):
        return jsonify({"error": "Filename contains invalid characters"}), 400
    
    new_path = os.path.join(os.path.dirname(old_path), base_name + ext)
    
    # Auto-suffix on name collision
    if os.path.exists(new_path) and os.path.realpath(new_path) != os.path.realpath(old_path):
        new_path = _unique_path(new_path)
    
    try:
        os.rename(old_path, new_path)
        final_name = os.path.basename(new_path)
        return jsonify({"success": True, "old_path": old_path, "new_path": new_path, "new_name": final_name})
    except Exception as e:
        return jsonify({"error": f"Rename failed: {e}"}), 500


@video_bp.route('/rename_folder', methods=['POST'])
def rename_folder():
    """Rename a folder"""
    data = request.json
    folder_path = data.get('path')
    new_name = data.get('new_name')
    
    if not folder_path or not new_name:
        return jsonify({"error": "path and new_name are required"}), 400
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({"error": f"Folder not found: {folder_path}"}), 404
    
    import re
    if not re.match(r'^[\w\u4e00-\u9fff\-. ]+$', new_name):
        return jsonify({"error": "Folder name contains invalid characters"}), 400
    
    new_path = os.path.join(os.path.dirname(folder_path), new_name)
    
    # Auto-suffix on name collision
    if os.path.exists(new_path) and os.path.realpath(new_path) != os.path.realpath(folder_path):
        new_path = _unique_path(new_path)
    
    try:
        os.rename(folder_path, new_path)
        final_name = os.path.basename(new_path)
        return jsonify({"success": True, "old_path": folder_path, "new_path": new_path, "new_name": final_name})
    except Exception as e:
        return jsonify({"error": f"Rename failed: {e}"}), 500


@video_bp.route('/delete_folder', methods=['POST'])
def delete_folder():
    """Delete a folder and all its contents (moves to recycle bin)"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import COMFYUI_PATH, REPO_ROOT, MOTIONSTREAMER_PATH, PRODISC_VAD_PATH, DATASET_PATH
    from services.trash_service import trash_folder
    
    data = request.json
    folder_path = data.get('path')
    
    if not folder_path:
        return jsonify({"error": "path is required"}), 400
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({"error": f"Folder not found: {folder_path}"}), 404
    
    # Safety check - prevent deleting critical system directories
    protected_paths = [
        COMFYUI_PATH,
        os.path.join(COMFYUI_PATH, 'output'),
        os.path.join(COMFYUI_PATH, 'output', 'video'),
        os.path.expanduser('~'),
        REPO_ROOT, MOTIONSTREAMER_PATH, PRODISC_VAD_PATH, DATASET_PATH,
    ]
    real_path = os.path.realpath(folder_path)
    for p in protected_paths:
        if real_path == os.path.realpath(p):
            return jsonify({"error": "Cannot delete system directory"}), 403
    
    try:
        entry = trash_folder(folder_path)
        if entry:
            return jsonify({"success": True, "deleted": folder_path, "file_count": entry.get("file_count", 0), "trash_id": entry["id"]})
        return jsonify({"error": "Failed to move to trash"}), 500
    except Exception as e:
        return jsonify({"error": f"Delete failed: {e}"}), 500
