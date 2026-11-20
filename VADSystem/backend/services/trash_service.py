"""Trash/Recycle Bin Service - moves deleted files to a recycle bin instead of permanent deletion"""
import os
import json
import shutil
import time
import uuid
import threading
import fcntl

import sys
from config import BASE_DIR
TRASH_DIR = os.path.expanduser("~/.Trash") if sys.platform == "darwin" else os.path.join(BASE_DIR, "recycle_bin")
TRASH_META_FILE = os.path.join(TRASH_DIR, ".trash_meta.json")
_meta_lock = threading.Lock()

os.makedirs(TRASH_DIR, exist_ok=True)


def _load_meta():
    """Load trash metadata (caller should hold _meta_lock for atomic read-modify-write)."""
    if os.path.exists(TRASH_META_FILE):
        try:
            with open(TRASH_META_FILE, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            return []
    return []


def _save_meta(meta):
    """Save trash metadata (caller should hold _meta_lock)."""
    with open(TRASH_META_FILE, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _append_entry(entry):
    """Append one entry to meta file atomically (avoids race when trashing multiple files)."""
    with _meta_lock:
        meta = _load_meta()
        meta.append(entry)
        _save_meta(meta)


def trash_file(file_path):
    """Move a file to the recycle bin. Returns trash entry or None."""
    if not os.path.exists(file_path):
        return None

    trash_id = uuid.uuid4().hex[:12]
    original_name = os.path.basename(file_path)
    # Keep extension for preview purposes
    _, ext = os.path.splitext(original_name)
    trash_name = f"{trash_id}{ext}"
    trash_path = os.path.join(TRASH_DIR, trash_name)

    shutil.move(file_path, trash_path)

    entry = {
        "id": trash_id,
        "original_name": original_name,
        "original_path": file_path,
        "trash_name": trash_name,
        "type": "file",
        "size": os.path.getsize(trash_path),
        "deleted_at": time.time(),
    }

    _append_entry(entry)
    return entry


def trash_folder(folder_path):
    """Move a folder to the recycle bin. Returns trash entry or None."""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return None

    trash_id = uuid.uuid4().hex[:12]
    original_name = os.path.basename(folder_path)
    trash_name = f"{trash_id}__{original_name}"
    trash_path = os.path.join(TRASH_DIR, trash_name)

    # Count files before moving
    file_count = sum(len(files) for _, _, files in os.walk(folder_path))
    folder_size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fns in os.walk(folder_path)
        for f in fns
    )

    shutil.move(folder_path, trash_path)

    entry = {
        "id": trash_id,
        "original_name": original_name,
        "original_path": folder_path,
        "trash_name": trash_name,
        "type": "folder",
        "file_count": file_count,
        "size": folder_size,
        "deleted_at": time.time(),
    }

    _append_entry(entry)
    return entry


def list_trash():
    """List all items in the recycle bin."""
    with _meta_lock:
        meta = _load_meta()
    # Filter out entries whose trash files no longer exist
    valid = []
    for entry in meta:
        trash_path = os.path.join(TRASH_DIR, entry["trash_name"])
        if os.path.exists(trash_path):
            valid.append(entry)
    if len(valid) != len(meta):
        with _meta_lock:
            _save_meta(valid)
    # Sort by deleted_at descending (newest first)
    valid.sort(key=lambda x: x.get("deleted_at", 0), reverse=True)
    return valid


def restore_item(trash_id):
    """Restore an item from the recycle bin to its original location."""
    with _meta_lock:
        meta = _load_meta()
    entry = next((e for e in meta if e["id"] == trash_id), None)
    if not entry:
        return {"success": False, "error": "Item not found in trash"}

    trash_path = os.path.join(TRASH_DIR, entry["trash_name"])
    if not os.path.exists(trash_path):
        with _meta_lock:
            meta = _load_meta()
            meta = [e for e in meta if e["id"] != trash_id]
            _save_meta(meta)
        return {"success": False, "error": "Trashed file no longer exists"}

    original_path = entry["original_path"]

    # Ensure parent directory exists
    parent_dir = os.path.dirname(original_path)
    os.makedirs(parent_dir, exist_ok=True)

    # If original path already exists, add a suffix
    if os.path.exists(original_path):
        base, ext = os.path.splitext(original_path)
        if entry["type"] == "folder":
            original_path = f"{original_path}_restored"
        else:
            original_path = f"{base}_restored{ext}"

    try:
        shutil.move(trash_path, original_path)
        with _meta_lock:
            meta = _load_meta()
            meta = [e for e in meta if e["id"] != trash_id]
            _save_meta(meta)
        return {"success": True, "restored_to": original_path}
    except Exception as e:
        return {"success": False, "error": f"Restore failed: {e}"}


def permanent_delete(trash_id):
    """Permanently delete an item from the recycle bin. Returns deleted_entry so caller can clear DB."""
    with _meta_lock:
        meta = _load_meta()
    entry = next((e for e in meta if e["id"] == trash_id), None)
    if not entry:
        return {"success": False, "error": "Item not found in trash"}

    trash_path = os.path.join(TRASH_DIR, entry["trash_name"])
    try:
        if os.path.isdir(trash_path):
            shutil.rmtree(trash_path)
        elif os.path.exists(trash_path):
            os.remove(trash_path)
        with _meta_lock:
            meta = _load_meta()
            meta = [e for e in meta if e["id"] != trash_id]
            _save_meta(meta)
        return {"success": True, "deleted_entry": entry}
    except Exception as e:
        return {"success": False, "error": f"Permanent delete failed: {e}"}


def permanent_delete_batch(trash_ids):
    """Permanently delete multiple items from the recycle bin. Returns deleted_entries for DB cleanup."""
    deleted = 0
    failed = 0
    deleted_entries = []
    for tid in trash_ids:
        result = permanent_delete(tid)
        if result["success"]:
            deleted += 1
            deleted_entries.append(result["deleted_entry"])
        else:
            failed += 1
    return {"success": True, "deleted": deleted, "failed": failed, "deleted_entries": deleted_entries}


def empty_trash():
    """Permanently delete everything in the recycle bin. Returns deleted_entries for DB cleanup."""
    with _meta_lock:
        meta = _load_meta()
    deleted = 0
    for entry in meta:
        trash_path = os.path.join(TRASH_DIR, entry["trash_name"])
        try:
            if os.path.isdir(trash_path):
                shutil.rmtree(trash_path)
            elif os.path.exists(trash_path):
                os.remove(trash_path)
            deleted += 1
        except:
            pass
    with _meta_lock:
        _save_meta([])
    return {"success": True, "deleted": deleted, "deleted_entries": meta}


def get_trash_size():
    """Get total size of the recycle bin."""
    total = 0
    for entry in os.scandir(TRASH_DIR):
        if entry.name.startswith('.'):
            continue
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            for dp, _, fns in os.walk(entry.path):
                for f in fns:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                    except:
                        pass
    return total
