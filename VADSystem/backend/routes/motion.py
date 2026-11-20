"""Motion API Routes"""
from flask import Blueprint, request, jsonify, send_file, Response
import os
import glob

motion_bp = Blueprint('motion', __name__)

@motion_bp.route('/directories', methods=['GET'])
def list_directories():
    """List all available motion directories (runs_*)"""
    from config import MOTIONSTREAMER_PATH
    
    directories = []
    pattern = os.path.join(MOTIONSTREAMER_PATH, "runs_*")
    
    for dir_path in glob.glob(pattern):
        if os.path.isdir(dir_path):
            dir_name = os.path.basename(dir_path)
            # Count motions in directory
            motion_count = 0
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    # Check if it has motion files
                    if os.path.exists(os.path.join(item_path, "motion_272_denorm.npy")):
                        motion_count += 1
            
            directories.append({
                "name": dir_name,
                "path": dir_path,
                "motion_count": motion_count
            })
    
    # Sort by name
    directories.sort(key=lambda x: x['name'])
    
    return jsonify({
        "directories": directories,
        "success": True
    })

@motion_bp.route('/generate', methods=['POST'])
def generate_motion():
    """Generate motion from text description"""
    from services.motion_service import MotionService
    
    data = request.json
    text = data.get('text', '')
    motion_id = data.get('motion_id', None)
    output_dir = data.get('output_dir', None)  # Target directory name (e.g., runs_sht_abnormal)
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    service = MotionService()
    result = service.generate_motion(text, motion_id, output_dir=output_dir)
    
    return jsonify(result)

@motion_bp.route('/render_mask', methods=['POST'])
def render_mask():
    """Render mask video from motion"""
    from services.motion_service import MotionService
    
    data = request.json
    motion_id = data.get('motion_id')
    background = data.get('background')
    yaw_deg = data.get('yaw', -60)  # Frontend sends as 'yaw'
    height = data.get('height', 1.5)
    distance = data.get('distance', 3.0)
    dataset = data.get('dataset', 'sht')
    render_name = data.get('render_name', None)  # Custom render name
    output_dir = data.get('output_dir', None)    # Output directory name (runs_*)
    video_width = data.get('video_width', 856)   # Video resolution width
    video_height = data.get('video_height', 480)  # Video resolution height
    
    if not motion_id:
        return jsonify({"error": "motion_id is required"}), 400
    
    service = MotionService()
    result = service.render_mask_video(
        motion_id=motion_id,
        background=background,
        yaw_deg=yaw_deg,
        height=height,
        distance=distance,
        dataset=dataset,
        render_name=render_name,
        output_dir=output_dir,
        video_width=video_width,
        video_height=video_height,
        source_directory=data.get('source_directory')
    )
    
    return jsonify(result)

@motion_bp.route('/task/<task_id>', methods=['GET'])
def get_task_progress(task_id):
    """Get progress of a motion generation or render task"""
    from services.motion_service import MotionService
    
    service = MotionService()
    progress = service.get_task_progress(task_id)
    
    return jsonify(progress)

@motion_bp.route('/list', methods=['GET'])
def list_motions():
    """List all generated motions with rendered video info"""
    from services.motion_service import MotionService
    from config import MOTIONSTREAMER_PATH
    
    # Support both 'dataset' (legacy) and 'directory' (new) parameters
    directory = request.args.get('directory', None)
    dataset = request.args.get('dataset', 'sht')
    
    service = MotionService()
    
    if directory:
        # Use custom directory
        dir_path = os.path.join(MOTIONSTREAMER_PATH, directory)
        motions = service.list_motions_from_dir(dir_path, directory)
        return jsonify({"motions": motions, "directory": directory, "success": True})
    else:
        # Legacy: use dataset-based directory
        if dataset in ['ucf-crime', 'ucf']:
            dataset = 'ucf'
        else:
            dataset = 'sht'
        
        motions = service.list_motions(dataset)
        return jsonify({"motions": motions, "dataset": dataset, "success": True})

@motion_bp.route('/status/<motion_id>', methods=['GET'])
def get_motion_status(motion_id):
    """Get status of a motion generation task"""
    from services.motion_service import MotionService
    
    service = MotionService()
    status = service.get_status(motion_id)
    
    return jsonify(status)

@motion_bp.route('/renders/<motion_id>', methods=['GET'])
def list_renders(motion_id):
    """List all renders for a specific motion"""
    from services.motion_service import MotionService
    
    dataset = request.args.get('dataset', 'sht')
    if dataset in ['ucf-crime', 'ucf']:
        dataset = 'ucf'
    else:
        dataset = 'sht'
    
    service = MotionService()
    renders = service.list_renders(motion_id, dataset)
    
    return jsonify({"renders": renders, "motion_id": motion_id, "success": True})

@motion_bp.route('/video/<motion_id>/<video_type>', methods=['GET'])
def get_video(motion_id, video_type):
    """Get rendered video file (composite or mask)"""
    from services.motion_service import MotionService
    
    render_id = request.args.get('render_id', None)
    dataset = request.args.get('dataset', None)
    
    service = MotionService()
    video_path = service.get_video_path(motion_id, video_type, dataset, render_id, request.args.get('directory'))
    
    if video_path and os.path.exists(video_path):
        return send_file(
            video_path,
            mimetype='video/mp4',
            as_attachment=False
        )
    
    return jsonify({"error": "Video not found"}), 404

@motion_bp.route('/delete/<motion_id>', methods=['DELETE', 'POST'])
def delete_motion(motion_id):
    """Delete a motion and its outputs.
    
    Returns 200 only when deletion succeeded, otherwise 4xx so frontend
    can treat it as a failed trash operation.
    """
    from services.motion_service import MotionService
    
    service = MotionService()
    result = service.delete_motion(motion_id)
    
    if result.get("success"):
        return jsonify(result), 200
    # Motion not found or failed to move to trash -> 400
    return jsonify(result), 400


@motion_bp.route('/server/status', methods=['GET'])
def motion_server_status():
    """Check motion server status"""
    from services.motion_service import MotionService
    service = MotionService()
    ready = service._is_motion_server_ready()
    return jsonify({"ready": ready, "url": "http://127.0.0.1:5100"})


@motion_bp.route('/server/start', methods=['POST'])
def start_motion_server():
    """Start the persistent motion server"""
    from services.motion_service import MotionService
    service = MotionService()
    if service._is_motion_server_ready():
        return jsonify({"success": True, "message": "Motion server is already running"})
    
    # Start in background — don't block the API request
    import threading
    def _start():
        service._start_motion_server()
    threading.Thread(target=_start, daemon=True).start()
    
    return jsonify({"success": True, "message": "Motion server is starting (models loading ~60-120s)..."})
