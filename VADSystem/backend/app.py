"""Main Flask Application for VAD System"""
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

# Import routes
from routes.motion import motion_bp
from routes.video import video_bp
from routes.train import train_bp
from routes.infer import infer_bp
from routes.analysis import analysis_bp
from routes.data import data_bp
from routes.auth import auth_bp
from routes.files import files_bp
from routes.trash import trash_bp
from routes.monitor import monitor_bp

# Import database
from database import init_db

DIST_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

def create_app():
    app = Flask(__name__, static_folder=DIST_DIR, static_url_path='')
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:6006", "http://localhost:6006"]}})
    
    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
    app.config['JSON_AS_ASCII'] = False
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['JWT_SECRET_KEY'] = os.environ['JWT_SECRET_KEY']
    if not app.config['SECRET_KEY'] or not app.config['JWT_SECRET_KEY']:
        raise ValueError('Set SECRET_KEY and JWT_SECRET_KEY environment variables before starting')
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    app.register_blueprint(motion_bp, url_prefix='/api/motion')
    app.register_blueprint(video_bp, url_prefix='/api/video')
    app.register_blueprint(train_bp, url_prefix='/api/train')
    app.register_blueprint(infer_bp, url_prefix='/api/infer')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(data_bp, url_prefix='/api/data')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(files_bp, url_prefix='/api/files')
    app.register_blueprint(trash_bp, url_prefix='/api/trash')
    app.register_blueprint(monitor_bp, url_prefix='/api/monitor')
    
    # Health check endpoint
    @app.route('/api/health')
    def health():
        return jsonify({
            "status": "ok",
            "message": "VAD System Backend is running"
        })
    
    # Serve frontend SPA
    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.errorhandler(404)
    def not_found(e):
        # For SPA client-side routing, serve index.html for non-API routes
        return send_from_directory(app.static_folder, 'index.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
