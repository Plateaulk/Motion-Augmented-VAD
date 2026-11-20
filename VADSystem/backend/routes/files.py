"""File Management API Routes - Database backed"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import os
import json

files_bp = Blueprint('files', __name__)

@files_bp.route('/paths', methods=['GET'])
def configured_paths():
    from config import COMFYUI_PATH, MOTIONSTREAMER_PATH, DATASET_PATH, CKPT_PATH
    return jsonify({"comfyui": COMFYUI_PATH, "motionstreamer": MOTIONSTREAMER_PATH,
                    "dataset": DATASET_PATH, "checkpoints": CKPT_PATH})



def clear_file_records_for_trash_path(original_path, is_folder=False):
    """Remove FileRecord(s) for this path so the same path can be reused after permanent delete from trash."""
    from database import db, FileRecord
    if not original_path:
        return 0
    try:
        if is_folder:
            prefix = original_path.rstrip(os.sep) + os.sep
            records = FileRecord.query.filter(
                (FileRecord.original_path == original_path) |
                (FileRecord.original_path.startswith(prefix))
            ).all()
        else:
            records = FileRecord.query.filter_by(original_path=original_path).all()
        for r in records:
            db.session.delete(r)
        db.session.commit()
        return len(records)
    except Exception:
        db.session.rollback()
        return 0


def get_current_user_id():
    """Get current user ID from token"""
    from routes.auth import verify_token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if payload:
            return payload.get('user_id')
    return None


def _safe_log_id(value):
    return ''.join(ch if ch.isalnum() else '_' for ch in value)


def _iter_log_files(root_dir, max_depth=0):
    if not root_dir or not os.path.isdir(root_dir):
        return

    root_dir = os.path.abspath(root_dir)
    root_depth = root_dir.rstrip(os.sep).count(os.sep)
    excluded_dirs = {
        '.git', '.cache', '.venv', '__pycache__', 'node_modules', 'dist',
        'recycle_bin', '.Trash', '.Trash-0'
    }

    for dirpath, dirnames, filenames in os.walk(root_dir):
        current_depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if max_depth is not None and current_depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs and not d.startswith('.')]

        for filename in filenames:
            if filename.endswith('.log'):
                yield os.path.join(dirpath, filename)


def _make_log_record(path, group_id, group_label, root_dir):
    stat_info = os.stat(path)
    rel_path = os.path.relpath(path, root_dir)
    return {
        "id": f"log_{_safe_log_id(group_id + '_' + rel_path)}",
        "name": os.path.basename(path),
        "type": "log",
        "path": path,
        "fullPath": path,
        "shortPath": f"{group_label}/{rel_path}",
        "size": stat_info.st_size,
        "modified": stat_info.st_mtime,
        "directory": group_id,
        "folderPath": [group_id],
        "group": group_label,
    }


@files_bp.route('/logs', methods=['GET'])
def list_logs():
    """List live log files used by the system file manager."""
    from config import BASE_DIR, PRODISC_VAD_PATH, MOTIONSTREAMER_PATH, COMFYUI_PATH

    sources = [
        ("system_logs", "System Logs", os.path.join(BASE_DIR, "logs"), 0),
        ("system_logs", "System Logs", os.path.join(BASE_DIR, "backend"), 0),
        ("training_logs", "Training Logs", os.path.join(PRODISC_VAD_PATH, "logs"), 1),
        ("batch_logs", "Batch Experiment Logs", os.path.join(PRODISC_VAD_PATH, "batch_experiments"), 4),
        ("motion_logs", "Motion Logs", MOTIONSTREAMER_PATH, 0),
        ("motion_logs", "Motion Logs", os.path.join(MOTIONSTREAMER_PATH, "runs_vad_system"), 3),
        ("comfyui_logs", "ComfyUI Logs", COMFYUI_PATH, 0),
    ]

    logs = []
    seen_paths = set()
    for group_id, group_label, root_dir, max_depth in sources:
        root_dir = os.path.abspath(root_dir)
        for path in _iter_log_files(root_dir, max_depth=max_depth):
            abs_path = os.path.abspath(path)
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            try:
                logs.append(_make_log_record(abs_path, group_id, group_label, root_dir))
            except OSError:
                continue

    logs.sort(key=lambda item: item["modified"], reverse=True)

    group_order = []
    for group_id, group_label, _, _ in sources:
        if group_id not in [g["id"] for g in group_order]:
            group_order.append({"id": group_id, "label": group_label})

    counts = {group["id"]: 0 for group in group_order}
    for item in logs:
        counts[item["directory"]] = counts.get(item["directory"], 0) + 1
    groups = [
        {"id": group["id"], "label": group["label"], "count": counts.get(group["id"], 0)}
        for group in group_order
    ]

    return jsonify({
        "success": True,
        "logs": logs,
        "groups": groups,
        "total": len(logs),
    })


@files_bp.route('/list', methods=['GET'])
def list_files():
    """List all file records from database"""
    from database import FileRecord
    
    file_type = request.args.get('type')  # background, video_ref, video_mask, feature, etc.
    category = request.args.get('category')
    dataset = request.args.get('dataset')
    include_deleted = request.args.get('include_deleted', 'false') == 'true'
    
    query = FileRecord.query
    
    if not include_deleted:
        query = query.filter_by(is_deleted=False)
    
    if file_type:
        query = query.filter_by(file_type=file_type)
    
    if category:
        query = query.filter_by(category=category)
    
    if dataset:
        query = query.filter_by(dataset=dataset)
    
    # Order by created_at desc
    query = query.order_by(FileRecord.created_at.desc())
    
    # Pagination parameters
    page = request.args.get('page', type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)  # Max 200 items per page
    
    # If pagination requested
    if page is not None:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            "success": True,
            "files": [f.to_dict() for f in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        })
    
    # No pagination - return all (for backward compatibility)
    files = query.all()
    
    return jsonify({
        "success": True,
        "files": [f.to_dict() for f in files],
        "total": len(files)
    })


@files_bp.route('/add', methods=['POST'])
def add_file():
    """Add a file record to database (copy reference, not actual file)"""
    from database import db, FileRecord
    
    data = request.json
    original_path = data.get('original_path')
    name = data.get('name')
    file_type = data.get('file_type')
    
    if not original_path or not name or not file_type:
        return jsonify({"error": "original_path, name, and file_type are required"}), 400
    
    # Check if file exists
    if not os.path.exists(original_path):
        return jsonify({"error": f"File not found: {original_path}"}), 404
    
    # Check if already exists in database
    existing = FileRecord.query.filter_by(original_path=original_path, is_deleted=False).first()
    if existing:
        return jsonify({"error": "File already in database", "file": existing.to_dict()}), 409
    
    # Get file size
    file_size = os.path.getsize(original_path)
    
    # Create record
    record = FileRecord(
        name=name,
        original_path=original_path,
        file_type=file_type,
        category=data.get('category'),
        tags=json.dumps(data.get('tags', [])),
        description=data.get('description'),
        file_size=file_size,
        mime_type=data.get('mime_type'),
        dataset=data.get('dataset'),
        user_id=get_current_user_id()
    )
    
    try:
        db.session.add(record)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "File added to database",
            "file": record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Add failed: {str(e)}"}), 500


@files_bp.route('/add_batch', methods=['POST'])
def add_files_batch():
    """Add multiple file records to database"""
    from database import db, FileRecord
    
    data = request.json
    files = data.get('files', [])
    
    if not files:
        return jsonify({"error": "No files provided"}), 400
    
    added = []
    skipped = []
    errors = []
    
    for file_data in files:
        original_path = file_data.get('original_path')
        name = file_data.get('name')
        file_type = file_data.get('file_type')
        
        if not original_path or not name or not file_type:
            errors.append({"file": file_data, "error": "Missing required fields"})
            continue
        
        if not os.path.exists(original_path):
            errors.append({"file": file_data, "error": "File not found"})
            continue
        
        # Check if already exists
        existing = FileRecord.query.filter_by(original_path=original_path, is_deleted=False).first()
        if existing:
            skipped.append({"file": file_data, "reason": "Already exists"})
            continue
        
        # Create record
        record = FileRecord(
            name=name,
            original_path=original_path,
            file_type=file_type,
            category=file_data.get('category'),
            tags=json.dumps(file_data.get('tags', [])),
            description=file_data.get('description'),
            file_size=os.path.getsize(original_path),
            mime_type=file_data.get('mime_type'),
            dataset=file_data.get('dataset'),
            user_id=get_current_user_id()
        )
        
        db.session.add(record)
        added.append(record)
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "added": len(added),
            "skipped": len(skipped),
            "errors": len(errors),
            "details": {
                "added": [f.to_dict() for f in added],
                "skipped": skipped,
                "errors": errors
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Batch add failed: {str(e)}"}), 500


@files_bp.route('/update/<int:file_id>', methods=['PUT'])
def update_file(file_id):
    """Update a file record"""
    from database import db, FileRecord
    
    record = FileRecord.query.get(file_id)
    if not record:
        return jsonify({"error": "File record not found"}), 404
    
    data = request.json
    
    if 'category' in data:
        record.category = data['category']
    if 'tags' in data:
        record.tags = json.dumps(data['tags'])
    if 'description' in data:
        record.description = data['description']
    if 'name' in data:
        record.name = data['name']
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Update successful",
            "file": record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Update failed: {str(e)}"}), 500


@files_bp.route('/delete/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Soft delete a file record (does not delete actual file)"""
    from database import db, FileRecord
    
    record = FileRecord.query.get(file_id)
    if not record:
        return jsonify({"error": "File record not found"}), 404
    
    record.is_deleted = True
    record.deleted_at = datetime.utcnow()
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Record deleted (file preserved)"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500


@files_bp.route('/restore/<int:file_id>', methods=['POST'])
def restore_file(file_id):
    """Restore a soft-deleted file record"""
    from database import db, FileRecord
    
    record = FileRecord.query.get(file_id)
    if not record:
        return jsonify({"error": "File record not found"}), 404
    
    record.is_deleted = False
    record.deleted_at = None
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Record restored",
            "file": record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500


@files_bp.route('/copy_to_category', methods=['POST'])
def copy_to_category():
    """Copy file records to a category (creates new records pointing to same file)"""
    from database import db, FileRecord
    
    data = request.json
    file_ids = data.get('file_ids', [])
    target_category = data.get('category')
    
    if not file_ids or not target_category:
        return jsonify({"error": "file_ids and category are required"}), 400
    
    copied = []
    
    for file_id in file_ids:
        original = FileRecord.query.get(file_id)
        if not original:
            continue
        
        # Create a new record pointing to the same file
        new_record = FileRecord(
            name=original.name,
            original_path=original.original_path,
            file_type=original.file_type,
            category=target_category,
            tags=original.tags,
            description=original.description,
            file_size=original.file_size,
            mime_type=original.mime_type,
            dataset=original.dataset,
            user_id=get_current_user_id()
        )
        db.session.add(new_record)
        copied.append(new_record)
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Copied {len(copied)} file(s) to {target_category}",
            "copied": [f.to_dict() for f in copied]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Copy failed: {str(e)}"}), 500


@files_bp.route('/move_to_category', methods=['POST'])
def move_to_category():
    """Move file records to a category (updates existing records)"""
    from database import db, FileRecord
    
    data = request.json
    file_ids = data.get('file_ids', [])
    target_category = data.get('category')
    
    if not file_ids or not target_category:
        return jsonify({"error": "file_ids and category are required"}), 400
    
    moved = 0
    
    for file_id in file_ids:
        record = FileRecord.query.get(file_id)
        if record:
            record.category = target_category
            moved += 1
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Moved {moved} file(s) to {target_category}",
            "moved": moved
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Move failed: {str(e)}"}), 500


# Collections/Folders management

@files_bp.route('/collections', methods=['GET'])
def list_collections():
    """List all collections"""
    from database import FileCollection
    
    user_id = get_current_user_id()
    query = FileCollection.query
    
    if user_id:
        query = query.filter((FileCollection.user_id == user_id) | (FileCollection.user_id == None))
    
    collections = query.all()
    return jsonify({
        "success": True,
        "collections": [c.to_dict() for c in collections]
    })


@files_bp.route('/collections', methods=['POST'])
def create_collection():
    """Create a new collection/folder"""
    from database import db, FileCollection
    
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({"error": "Collection name is required"}), 400
    
    collection = FileCollection(
        name=name,
        description=data.get('description'),
        parent_id=data.get('parent_id'),
        user_id=get_current_user_id()
    )
    
    try:
        db.session.add(collection)
        db.session.commit()
        return jsonify({
            "success": True,
            "collection": collection.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Create failed: {str(e)}"}), 500


@files_bp.route('/collections/<int:collection_id>/files', methods=['POST'])
def add_files_to_collection(collection_id):
    """Add files to a collection"""
    from database import db, FileCollection, FileCollectionItem
    
    collection = FileCollection.query.get(collection_id)
    if not collection:
        return jsonify({"error": "Collection not found"}), 404
    
    data = request.json
    file_ids = data.get('file_ids', [])
    
    added = 0
    for file_id in file_ids:
        # Check if already in collection
        existing = FileCollectionItem.query.filter_by(
            file_record_id=file_id,
            collection_id=collection_id
        ).first()
        
        if not existing:
            item = FileCollectionItem(
                file_record_id=file_id,
                collection_id=collection_id
            )
            db.session.add(item)
            added += 1
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Added {added} file(s) to collection",
            "added": added
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Add failed: {str(e)}"}), 500


@files_bp.route('/collections/<int:collection_id>/files', methods=['GET'])
def get_collection_files(collection_id):
    """Get all files in a collection"""
    from database import FileCollection, FileCollectionItem, FileRecord
    
    collection = FileCollection.query.get(collection_id)
    if not collection:
        return jsonify({"error": "Collection not found"}), 404
    
    items = FileCollectionItem.query.filter_by(collection_id=collection_id).all()
    files = [item.file_record.to_dict() for item in items if item.file_record and not item.file_record.is_deleted]
    
    return jsonify({
        "success": True,
        "collection": collection.to_dict(),
        "files": files
    })


@files_bp.route('/categories', methods=['GET'])
def list_categories():
    """List all unique categories"""
    from database import db, FileRecord
    
    categories = db.session.query(FileRecord.category).filter(
        FileRecord.is_deleted == False,
        FileRecord.category != None
    ).distinct().all()
    
    return jsonify({
        "success": True,
        "categories": [c[0] for c in categories if c[0]]
    })


@files_bp.route('/scan', methods=['POST'])
def scan_and_add_files():
    """Scan a directory and add files to database"""
    from database import db, FileRecord
    import glob
    
    data = request.json
    directory = data.get('directory')
    file_type = data.get('file_type')
    pattern = data.get('pattern', '*')  # glob pattern
    dataset = data.get('dataset')
    category = data.get('category')
    
    if not directory or not file_type:
        return jsonify({"error": "directory and file_type are required"}), 400
    
    if not os.path.isdir(directory):
        return jsonify({"error": f"Directory not found: {directory}"}), 404
    
    # Scan directory
    search_pattern = os.path.join(directory, '**', pattern)
    files_found = glob.glob(search_pattern, recursive=True)
    
    added = []
    skipped = []
    
    for file_path in files_found:
        if not os.path.isfile(file_path):
            continue
        
        # Check if already exists
        existing = FileRecord.query.filter_by(original_path=file_path, is_deleted=False).first()
        if existing:
            skipped.append(file_path)
            continue
        
        record = FileRecord(
            name=os.path.basename(file_path),
            original_path=file_path,
            file_type=file_type,
            category=category,
            file_size=os.path.getsize(file_path),
            dataset=dataset,
            user_id=get_current_user_id()
        )
        db.session.add(record)
        added.append(record)
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "scanned": len(files_found),
            "added": len(added),
            "skipped": len(skipped),
            "files": [f.to_dict() for f in added]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Scan add failed: {str(e)}"}), 500


@files_bp.route('/upload', methods=['POST'])
def upload_files():
    """Upload files to a specific category"""
    from database import db, FileRecord
    from config import (
        SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR,
        SHT_SYNTHETIC_VIDEO_DIR, UCF_SYNTHETIC_VIDEO_DIR
    )
    from werkzeug.utils import secure_filename
    import shutil
    
    if 'files' not in request.files:
        return jsonify({"error": "No files"}), 400
    
    files = request.files.getlist('files')
    category = request.form.get('category')
    dataset = request.form.get('dataset', 'sht')
    
    if not category:
        return jsonify({"error": "Select category"}), 400
    
    # Determine upload directory based on category and dataset
    if category == 'background':
        if dataset == 'ucf':
            upload_dir = UCF_BACKGROUND_DIR
        else:
            upload_dir = SHT_BACKGROUND_DIR
    elif category in ['video_ref', 'video_mask', 'video_gen']:
        if dataset == 'ucf':
            upload_dir = UCF_SYNTHETIC_VIDEO_DIR
        else:
            upload_dir = SHT_SYNTHETIC_VIDEO_DIR
        # Create subdirectory for video type
        if category == 'video_ref':
            upload_dir = os.path.join(upload_dir, 'reference')
        elif category == 'video_mask':
            upload_dir = os.path.join(upload_dir, 'mask')
        else:
            upload_dir = os.path.join(upload_dir, 'generated')
    elif category == 'feature':
        # Use a default feature directory
        if dataset == 'ucf':
            from config import UCF_FEATURE_SYSTEM_DIR
            upload_dir = UCF_FEATURE_SYSTEM_DIR
        else:
            from config import SHT_FEATURE_SYSTEM_DIR
            upload_dir = SHT_FEATURE_SYSTEM_DIR
    else:
        return jsonify({"error": f"Unsupported category: {category}"}), 400
    
    # Create directory if not exists
    os.makedirs(upload_dir, exist_ok=True)
    
    uploaded = []
    errors = []
    
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, filename)
            
            # Handle duplicate filenames
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{base}_{counter}{ext}"
                filepath = os.path.join(upload_dir, filename)
                counter += 1
            
            try:
                file.save(filepath)
                
                # Add to database
                record = FileRecord(
                    filename=filename,
                    filepath=filepath,
                    file_type=category,
                    category=category,
                    file_size=os.path.getsize(filepath),
                    dataset=dataset,
                    user_id=get_current_user_id()
                )
                db.session.add(record)
                uploaded.append(filename)
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
    return jsonify({
        "success": True,
        "uploaded": len(uploaded),
        "files": uploaded,
        "errors": errors if errors else None
    })


@files_bp.route('/folders', methods=['GET'])
def list_folders():
    """List all folders by category - shows all files regardless of dataset"""
    from config import (
        SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR, SYSTEM_BACKGROUND_DIR,
        VIDEO_OUTPUT_DIR, VIDEO_SYSTEM_FOLDER,
        MOTIONSTREAMER_PATH, MOTION_OUTPUT_DIR,
        SHT_FEATURE_SYSTEM_DIR, UCF_FEATURE_SYSTEM_DIR, DATASET_PATH
    )
    import glob
    
    folders = {
        'background': [],
        'motion': [],
        'mask_pair': [],
        'video_gen': [],
        'feature': []
    }
    
    # Background folders - include all (SHT, UCF, System)
    # System folder first
    folders['background'].append({'name': 'system_background', 'label': 'System Background', 'is_system': True})
    
    for bg_dir, label in [(SHT_BACKGROUND_DIR, 'SHT Background'), (UCF_BACKGROUND_DIR, 'UCF Background')]:
        if os.path.exists(bg_dir):
            dir_name = os.path.basename(bg_dir)
            folders['background'].append({'name': dir_name, 'label': label, 'is_system': False})
            # Check for subdirectories (exclude .thumbs)
            for item in sorted(os.listdir(bg_dir)):
                if os.path.isdir(os.path.join(bg_dir, item)) and not item.startswith('.'):
                    folders['background'].append({'name': f"{dir_name}/{item}", 'label': f"{label}/{item}", 'is_system': False})
    
    # Video folders - system folder first, then all others
    folders['video_gen'].append({'name': VIDEO_SYSTEM_FOLDER, 'label': 'System Generated', 'is_system': True})
    if os.path.exists(VIDEO_OUTPUT_DIR):
        for item in sorted(os.listdir(VIDEO_OUTPUT_DIR)):
            item_path = os.path.join(VIDEO_OUTPUT_DIR, item)
            if os.path.isdir(item_path) and not item.startswith('.') and item != VIDEO_SYSTEM_FOLDER:
                folders['video_gen'].append({'name': item, 'label': item, 'is_system': False})
    
    # Feature folders - system folders first
    folders['feature'].append({'name': 'shanghaitech/SH_clip_video_features/system_extracted', 'label': 'System Feature (SHT)', 'is_system': True})
    folders['feature'].append({'name': 'ucf-crime/UCFClipFeatures/system_extracted', 'label': 'System Feature (UCF)', 'is_system': True})
    
    # Scan feature directories: root dirs + their sub-directories
    if os.path.exists(DATASET_PATH):
        for dataset_name in sorted(os.listdir(DATASET_PATH)):
            dataset_path = os.path.join(DATASET_PATH, dataset_name)
            if not os.path.isdir(dataset_path):
                continue
            for item in sorted(os.listdir(dataset_path)):
                item_path = os.path.join(dataset_path, item)
                if os.path.isdir(item_path) and ('feature' in item.lower() or 'clip' in item.lower()):
                    # Add root feature directory
                    root_folder_name = f"{dataset_name}/{item}"
                    folders['feature'].append({'name': root_folder_name, 'label': root_folder_name, 'is_system': False, 'is_root': True})
                    # Scan subdirs (exclude system_extracted)
                    for sub in sorted(os.listdir(item_path)):
                        sub_path = os.path.join(item_path, sub)
                        if os.path.isdir(sub_path) and sub != 'system_extracted' and not sub.startswith('.'):
                            sub_folder_name = f"{dataset_name}/{item}/{sub}"
                            folders['feature'].append({'name': sub_folder_name, 'label': sub, 'is_system': False, 'is_root': False})
    
    # Motion folders - system folder first
    folders['motion'].append({'name': 'runs_vad_system', 'label': 'System Motion', 'is_system': True})
    folders['mask_pair'].append({'name': 'runs_vad_system', 'label': 'System Mask Pair', 'is_system': True})
    
    for dir_path in sorted(glob.glob(os.path.join(MOTIONSTREAMER_PATH, "runs_*"))):
        if os.path.isdir(dir_path):
            dir_name = os.path.basename(dir_path)
            if dir_name != 'runs_vad_system':
                folders['motion'].append({'name': dir_name, 'label': dir_name, 'is_system': False})
                folders['mask_pair'].append({'name': dir_name, 'label': dir_name, 'is_system': False})
    
    return jsonify({
        "success": True,
        "folders": folders
    })


@files_bp.route('/create_folder', methods=['POST'])
def create_folder():
    """Create a new folder in a category"""
    from config import (
        SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR,
        SHT_SYNTHETIC_VIDEO_DIR, UCF_SYNTHETIC_VIDEO_DIR,
        MOTIONSTREAMER_PATH,
        SHT_FEATURE_PATH, UCF_FEATURE_PATH,
        CKPT_PATH
    )
    
    data = request.json
    category = data.get('category')
    folder_name = data.get('folder_name')
    dataset = data.get('dataset', 'sht')
    
    if not category or not folder_name:
        return jsonify({"error": "Category and folder name required"}), 400
    
    # Sanitize folder name
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', folder_name):
        return jsonify({"error": "Folder name: only letters, numbers, _ and - allowed"}), 400
    
    # Determine base directory
    if category == 'background':
        base_dir = UCF_BACKGROUND_DIR if dataset == 'ucf' else SHT_BACKGROUND_DIR
    elif category == 'video_ref':
        base_dir = os.path.join(UCF_SYNTHETIC_VIDEO_DIR if dataset == 'ucf' else SHT_SYNTHETIC_VIDEO_DIR, 'reference')
    elif category == 'video_mask':
        base_dir = os.path.join(UCF_SYNTHETIC_VIDEO_DIR if dataset == 'ucf' else SHT_SYNTHETIC_VIDEO_DIR, 'mask')
    elif category == 'video_gen':
        base_dir = os.path.join(UCF_SYNTHETIC_VIDEO_DIR if dataset == 'ucf' else SHT_SYNTHETIC_VIDEO_DIR, 'generated')
    elif category in ('motion', 'mask_pair'):
        # Motion and mask pair share same dir structure
        base_dir = MOTIONSTREAMER_PATH
        folder_name = f"runs_{folder_name}" if not folder_name.startswith("runs_") else folder_name
    elif category in ('feature', 'feature_vad'):
        # Feature dir under root feature dir
        base_dir = UCF_FEATURE_PATH if dataset == 'ucf' else SHT_FEATURE_PATH
    elif category == 'model':
        # Model dir under ckpt dir
        base_dir = CKPT_PATH
    else:
        return jsonify({"error": f"Unsupported category: {category}"}), 400
    
    # Create folder - auto-suffix on name collision
    folder_path = os.path.join(base_dir, folder_name)
    original_name = folder_name
    counter = 1
    while os.path.exists(folder_path):
        counter += 1
        folder_name = f"{original_name}_{counter}"
    folder_path = os.path.join(base_dir, folder_name)
    
    try:
        os.makedirs(folder_path, exist_ok=True)
        return jsonify({
            "success": True,
            "folder_path": folder_path,
            "folder_name": folder_name
        })
    except Exception as e:
        return jsonify({"error": f"Create failed: {str(e)}"}), 500


@files_bp.route('/browse', methods=['GET'])
def browse_directory():
    """Browse a directory and list files/subdirectories
    
    Query params:
        path: The directory path to browse (required)
        show_hidden: Whether to show hidden files (default: false)
    """
    import stat
    from pathlib import Path
    
    dir_path = request.args.get('path', '')
    show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
    
    if not dir_path:
        # Return root directories for browsing
        return jsonify({
            "success": True,
            "path": "/",
            "parent": None,
            "items": [
                {"name": "root", "path": "/root", "type": "directory"},
                {"name": "tmp", "path": "/tmp", "type": "directory"},
            ]
        })
    
    # Normalize path
    dir_path = os.path.abspath(dir_path)
    
    if not os.path.exists(dir_path):
        return jsonify({"error": f"Path not found: {dir_path}"}), 404
    
    if not os.path.isdir(dir_path):
        return jsonify({"error": f"Not a directory: {dir_path}"}), 400
    
    try:
        items = []
        for name in sorted(os.listdir(dir_path)):
            # Skip hidden files unless requested
            if not show_hidden and name.startswith('.'):
                continue
            
            item_path = os.path.join(dir_path, name)
            try:
                stat_info = os.stat(item_path)
                is_dir = stat.S_ISDIR(stat_info.st_mode)
                
                item = {
                    "name": name,
                    "path": item_path,
                    "type": "directory" if is_dir else "file",
                    "size": stat_info.st_size if not is_dir else None,
                    "modified": stat_info.st_mtime
                }
                
                # Add file extension for files
                if not is_dir:
                    ext = os.path.splitext(name)[1].lower()
                    item["extension"] = ext
                    # Check if it's a supported file type
                    if ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv']:
                        item["file_type"] = "video"
                    elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                        item["file_type"] = "image"
                    elif ext in ['.npy', '.npz', '.pt', '.pth']:
                        item["file_type"] = "feature"
                    elif ext in ['.json', '.txt', '.csv']:
                        item["file_type"] = "text"
                    else:
                        item["file_type"] = "other"
                else:
                    # Count items in directory
                    try:
                        child_items = os.listdir(item_path)
                        item["child_count"] = len([c for c in child_items if not c.startswith('.')])
                    except:
                        item["child_count"] = 0
                
                items.append(item)
            except (PermissionError, OSError):
                # Skip inaccessible items.
                continue
        
        # Separate directories and files, directories first
        directories = [i for i in items if i["type"] == "directory"]
        files = [i for i in items if i["type"] == "file"]
        
        # Get parent directory
        parent_path = os.path.dirname(dir_path)
        if parent_path == dir_path:  # Root directory
            parent_path = None
        
        return jsonify({
            "success": True,
            "path": dir_path,
            "parent": parent_path,
            "items": directories + files,
            "directory_count": len(directories),
            "file_count": len(files)
        })
    except PermissionError:
        return jsonify({"error": f"No permission: {dir_path}"}), 403
    except Exception as e:
        return jsonify({"error": f"Browse failed: {str(e)}"}), 500


@files_bp.route('/download', methods=['GET'])
def download_file():
    """Download a file by its absolute path.
    
    Query params:
        path: Absolute path of the file to download (required)
    """
    from flask import send_file
    
    file_path = request.args.get('path', '')
    if not file_path:
        return jsonify({"error": "File path required"}), 400
    
    file_path = os.path.abspath(file_path)
    
    # Security check: only allow files under known project directories
    from config import PRODISC_VAD_PATH, DATASET_PATH, BASE_DIR, COMFYUI_PATH, MOTIONSTREAMER_PATH
    allowed_prefixes = [
        os.path.abspath(PRODISC_VAD_PATH),
        os.path.abspath(DATASET_PATH),
        BASE_DIR, COMFYUI_PATH, MOTIONSTREAMER_PATH
    ]
    
    is_allowed = any(os.path.commonpath([os.path.realpath(file_path), os.path.realpath(prefix)]) == os.path.realpath(prefix) for prefix in allowed_prefixes)
    if not is_allowed:
        return jsonify({"error": "Download not allowed for this path"}), 403
    
    if not os.path.exists(file_path):
        return jsonify({"error": f"File not found: {file_path}"}), 404
    
    if not os.path.isfile(file_path):
        return jsonify({"error": "Can only download files, not directories"}), 400
    
    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )
    except Exception as e:
        return jsonify({"error": f"Download failed: {str(e)}"}), 500


