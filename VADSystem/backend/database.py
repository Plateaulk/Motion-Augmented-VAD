"""Database module for VAD System"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to file records
    file_records = db.relationship('FileRecord', backref='owner', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }


class FileRecord(db.Model):
    """File record model - stores metadata about files without moving them"""
    __tablename__ = 'file_records'
    
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    
    # File metadata
    name = db.Column(db.String(255), nullable=False, index=True)
    original_path = db.Column(db.String(500), nullable=False, index=True)  # Original file location
    file_type = db.Column(db.String(50), nullable=False, index=True)  # background, video_ref, video_mask, video_gen, feature, motion
    
    # Organizational metadata
    category = db.Column(db.String(100), index=True)  # User-defined category/folder
    tags = db.Column(db.Text)  # JSON array of tags
    description = db.Column(db.Text)
    
    # File info
    file_size = db.Column(db.BigInteger)
    mime_type = db.Column(db.String(100))
    
    # Dataset association
    dataset = db.Column(db.String(50), index=True)  # sht, ucf
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Owner
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    deleted_at = db.Column(db.DateTime)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        db.Index('idx_file_type_dataset', 'file_type', 'dataset', 'is_deleted'),
        db.Index('idx_category_type', 'category', 'file_type', 'is_deleted'),
        db.Index('idx_user_files', 'user_id', 'file_type', 'is_deleted'),
    )
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'file_id': self.file_id,
            'name': self.name,
            'original_path': self.original_path,
            'file_type': self.file_type,
            'category': self.category,
            'tags': json.loads(self.tags) if self.tags else [],
            'description': self.description,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'dataset': self.dataset,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id,
            'is_deleted': self.is_deleted
        }


class FileCollection(db.Model):
    """Collection/folder for organizing files"""
    __tablename__ = 'file_collections'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('file_collections.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for nested collections
    children = db.relationship('FileCollection', backref=db.backref('parent', remote_side=[id]))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FileCollectionItem(db.Model):
    """Many-to-many relationship between files and collections"""
    __tablename__ = 'file_collection_items'
    
    id = db.Column(db.Integer, primary_key=True)
    file_record_id = db.Column(db.Integer, db.ForeignKey('file_records.id'), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('file_collections.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    file_record = db.relationship('FileRecord', backref='collection_items')
    collection = db.relationship('FileCollection', backref='items')


def init_db(app):
    """Initialize the database"""
    import os
    
    # Database path
    db_path = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vad_system.db'))
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # SQLite performance optimizations
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {
            'check_same_thread': False,
        },
        'pool_pre_ping': True,
    }
    
    db.init_app(app)
    
    with app.app_context():
        # SQLite specific optimizations
        from sqlalchemy import event
        
        @event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # Enable WAL mode for better concurrent read/write performance
            cursor.execute("PRAGMA journal_mode=WAL")
            # Increase cache size (negative value means KB, -64000 = 64MB)
            cursor.execute("PRAGMA cache_size=-64000")
            # Synchronous mode: NORMAL is a good balance of safety and speed
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Enable memory-mapped I/O for faster reads
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
            # Temp store in memory
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
        
        db.create_all()
        
        # Register an account through the UI; no shared default credentials.

    return db
