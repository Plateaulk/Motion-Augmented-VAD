"""Monitor API Routes - Real-time camera monitoring
Frontend captures frames via getUserMedia, sends to backend for analysis"""
from flask import Blueprint, request, jsonify

monitor_bp = Blueprint('monitor', __name__)


@monitor_bp.route('/preload', methods=['POST'])
def preload_monitor():
    """Warm up CLIP + VAD model before the user starts monitoring."""
    from services.monitor_service import MonitorManager

    data = request.json or {}
    model_id = data.get('model_id', '')

    if not model_id:
        return jsonify({"error": "Please select a detection model", "success": False}), 400

    manager = MonitorManager.get_instance()
    result = manager.preload(model_id)

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 409


@monitor_bp.route('/start', methods=['POST'])
def start_monitor():
    """Initialize monitoring session: load CLIP + VAD model"""
    from services.monitor_service import MonitorManager

    data = request.json or {}
    model_id = data.get('model_id', '')
    threshold = data.get('threshold', 0.5)

    if not model_id:
        return jsonify({"error": "Please select a detection model", "success": False}), 400

    try:
        threshold = float(threshold)
    except (ValueError, TypeError):
        threshold = 0.5

    manager = MonitorManager.get_instance()
    result = manager.start(model_id, threshold)

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 409


@monitor_bp.route('/stop', methods=['POST'])
def stop_monitor():
    """Stop monitoring session"""
    from services.monitor_service import MonitorManager

    manager = MonitorManager.get_instance()
    result = manager.stop()
    return jsonify(result)


@monitor_bp.route('/analyze_frame', methods=['POST'])
def analyze_frame():
    """Receive a camera frame from browser, return anomaly score

    Request body:
        frame (str): base64-encoded camera image (data URL or raw base64)
        model_id (str): anomaly detection model ID
        threshold (float): anomaly alert threshold
    """
    from services.monitor_service import MonitorManager

    data = request.json or {}
    frame = data.get('frame', '')
    model_id = data.get('model_id', '')
    threshold = data.get('threshold', 0.5)

    if not frame:
        return jsonify({"error": "No frame data received", "success": False}), 400
    if not model_id:
        return jsonify({"error": "Model not specified", "success": False}), 400

    try:
        threshold = float(threshold)
    except (ValueError, TypeError):
        threshold = 0.5

    manager = MonitorManager.get_instance()
    result = manager.analyze_frame(frame, model_id, threshold)

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@monitor_bp.route('/status', methods=['GET'])
def get_status():
    """Get current monitoring status"""
    from services.monitor_service import MonitorManager

    manager = MonitorManager.get_instance()

    return jsonify(manager.status())
