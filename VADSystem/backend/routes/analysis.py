"""Analysis API Routes"""
from flask import Blueprint, request, jsonify

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/auc', methods=['POST'])
def calculate_auc():
    """Calculate AUC score"""
    from services.analysis_service import AnalysisService
    
    data = request.json
    predictions = data.get('predictions')
    ground_truth = data.get('ground_truth')
    dataset = data.get('dataset', 'shanghaitech')
    
    service = AnalysisService()
    result = service.calculate_auc(predictions, ground_truth, dataset)
    
    return jsonify(result)

@analysis_bp.route('/compare', methods=['POST'])
def compare_models():
    """Compare multiple models"""
    from services.analysis_service import AnalysisService
    
    data = request.json
    model_results = data.get('model_results', {})
    dataset = data.get('dataset', 'shanghaitech')
    
    service = AnalysisService()
    result = service.compare_models(model_results, dataset)
    
    return jsonify(result)

@analysis_bp.route('/frame_scores', methods=['POST'])
def get_frame_scores():
    """Get frame-level anomaly scores"""
    from services.analysis_service import AnalysisService
    
    data = request.json
    video_name = data.get('video_name')
    predictions = data.get('predictions')
    
    if not video_name or not predictions:
        return jsonify({"error": "video_name and predictions are required"}), 400
    
    service = AnalysisService()
    result = service.get_frame_scores(video_name, predictions)
    
    return jsonify(result)

@analysis_bp.route('/heatmap', methods=['POST'])
def generate_heatmap():
    """Generate anomaly heatmap data"""
    from services.analysis_service import AnalysisService
    
    data = request.json
    video_name = data.get('video_name')
    predictions = data.get('predictions')
    
    if not video_name or not predictions:
        return jsonify({"error": "video_name and predictions are required"}), 400
    
    service = AnalysisService()
    result = service.generate_heatmap(video_name, predictions)
    
    return jsonify(result)

@analysis_bp.route('/ground_truth', methods=['GET'])
def get_ground_truth():
    """Get ground truth labels for dataset"""
    from services.analysis_service import AnalysisService
    
    dataset = request.args.get('dataset', 'shanghaitech')
    video_name = request.args.get('video_name', None)
    
    service = AnalysisService()
    result = service.get_ground_truth(dataset, video_name)
    
    return jsonify(result)


@analysis_bp.route('/infer_score', methods=['GET'])
def get_infer_score():
    """Get inference score curve with aligned ground-truth regions."""
    from services.analysis_service import AnalysisService

    dataset = request.args.get('dataset', 'shanghaitech')
    model_id = request.args.get('model_id')
    video_name = request.args.get('video_name', None)

    if not model_id:
        return jsonify({"error": "model_id is required"}), 400

    service = AnalysisService()
    result = service.get_infer_score_plot(dataset, model_id, video_name)

    return jsonify(result)

@analysis_bp.route('/summary', methods=['GET'])
def get_summary():
    """Get summary statistics for all models"""
    from services.analysis_service import AnalysisService
    
    dataset = request.args.get('dataset', 'shanghaitech')
    
    service = AnalysisService()
    result = service.get_summary(dataset)
    
    return jsonify(result)


@analysis_bp.route('/training_curve/<model_id>', methods=['GET'])
def get_training_curve(model_id):
    """Get training curve data for a specific model"""
    from services.analysis_service import AnalysisService
    
    service = AnalysisService()
    result = service.get_training_curve(model_id)
    
    return jsonify(result)


@analysis_bp.route('/comparison', methods=['GET'])
def get_comparison():
    """Get comparison data for all models in dataset"""
    from services.analysis_service import AnalysisService
    
    dataset = request.args.get('dataset', 'shanghaitech')
    
    service = AnalysisService()
    result = service.get_comparison_data(dataset)
    
    return jsonify(result)
