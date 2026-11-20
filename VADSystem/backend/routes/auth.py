"""Authentication API Routes"""
from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime
import jwt
import os

auth_bp = Blueprint('auth', __name__)

# JWT secret is loaded by the application from the local environment.

def generate_token(user_id, username):
    """Generate JWT token"""
    import datetime as dt
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': dt.datetime.utcnow() + dt.timedelta(days=7)
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    from database import db, User
    
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    # Validation
    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    
    if not email or '@' not in email:
        return jsonify({"error": "Please enter a valid email"}), 400
    
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    
    # Check if user exists
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        if existing_user.username == username:
            return jsonify({"error": "Username already exists"}), 400
        else:
            return jsonify({"error": "Email already registered"}), 400
    
    # Create new user
    try:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Generate token
        token = generate_token(user.id, user.username)
        
        return jsonify({
            "success": True,
            "message": "Registration successful",
            "user": user.to_dict(),
            "token": token
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    from database import db, User
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Find user by username or email
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401
    
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = generate_token(user.id, user.username)
    
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": user.to_dict(),
        "token": token
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    # With JWT, logout is handled client-side by removing the token
    return jsonify({
        "success": True,
        "message": "Logged out"
    })


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """Get current user info"""
    from database import User
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Not logged in"}), 401
    
    token = auth_header.split(' ')[1]
    payload = verify_token(token)
    
    if not payload:
        return jsonify({"error": "Session expired, please login again"}), 401
    
    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "success": True,
        "user": user.to_dict()
    })


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    from database import db, User
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Not logged in"}), 401
    
    token = auth_header.split(' ')[1]
    payload = verify_token(token)
    
    if not payload:
        return jsonify({"error": "Session expired"}), 401
    
    data = request.json
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({"error": "Old and new password required"}), 400
    
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400
    
    user = User.query.get(payload['user_id'])
    if not user or not user.check_password(old_password):
        return jsonify({"error": "Incorrect old password"}), 401
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Password changed successfully"
    })


@auth_bp.route('/users', methods=['GET'])
def list_users():
    """List all users (admin only)"""
    from database import User
    
    # Simple admin check - in production, use proper role-based access
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Not logged in"}), 401
    
    token = auth_header.split(' ')[1]
    payload = verify_token(token)
    
    if not payload:
        return jsonify({"error": "Session expired"}), 401
    
    # Check if user is admin
    if payload.get('username') != 'admin':
        return jsonify({"error": "Insufficient permissions"}), 403
    
    users = User.query.all()
    return jsonify({
        "success": True,
        "users": [u.to_dict() for u in users]
    })
