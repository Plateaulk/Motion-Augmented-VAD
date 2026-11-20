"""Trash / Recycle Bin API routes"""
from flask import Blueprint, request, jsonify
from services.trash_service import (
    list_trash, restore_item, permanent_delete,
    permanent_delete_batch, empty_trash, get_trash_size,
)
from routes.files import clear_file_records_for_trash_path

trash_bp = Blueprint('trash', __name__)


@trash_bp.route('/list', methods=['GET'])
def trash_list():
    """List all items in the recycle bin."""
    items = list_trash()
    total_size = get_trash_size()
    return jsonify({"items": items, "count": len(items), "total_size": total_size})


@trash_bp.route('/restore', methods=['POST'])
def trash_restore():
    """Restore an item from the recycle bin."""
    data = request.json
    trash_id = data.get('id')
    if not trash_id:
        return jsonify({"error": "id is required"}), 400
    result = restore_item(trash_id)
    if result["success"]:
        return jsonify(result)
    return jsonify(result), 400


@trash_bp.route('/restore_batch', methods=['POST'])
def trash_restore_batch():
    """Restore multiple items from the recycle bin."""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"error": "ids is required"}), 400
    restored = 0
    failed = 0
    for tid in ids:
        result = restore_item(tid)
        if result["success"]:
            restored += 1
        else:
            failed += 1
    return jsonify({"success": True, "restored": restored, "failed": failed})


@trash_bp.route('/delete', methods=['POST'])
def trash_delete():
    """Permanently delete an item from the recycle bin. Clears DB records so same path can be reused."""
    data = request.json
    trash_id = data.get('id')
    if not trash_id:
        return jsonify({"error": "id is required"}), 400
    result = permanent_delete(trash_id)
    if result["success"]:
        entry = result.get("deleted_entry")
        if entry:
            clear_file_records_for_trash_path(
                entry.get("original_path"),
                is_folder=(entry.get("type") == "folder")
            )
        return jsonify({"success": True})
    return jsonify(result), 400


@trash_bp.route('/delete_batch', methods=['POST'])
def trash_delete_batch():
    """Permanently delete multiple items from the recycle bin. Clears DB records so paths can be reused."""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"error": "ids is required"}), 400
    result = permanent_delete_batch(ids)
    if result.get("deleted_entries"):
        for entry in result["deleted_entries"]:
            clear_file_records_for_trash_path(
                entry.get("original_path"),
                is_folder=(entry.get("type") == "folder")
            )
    return jsonify({"success": True, "deleted": result["deleted"], "failed": result["failed"]})


@trash_bp.route('/empty', methods=['POST'])
def trash_empty():
    """Empty the recycle bin. Clears DB records so paths can be reused."""
    result = empty_trash()
    if result.get("deleted_entries"):
        for entry in result["deleted_entries"]:
            clear_file_records_for_trash_path(
                entry.get("original_path"),
                is_folder=(entry.get("type") == "folder")
            )
    return jsonify({"success": True, "deleted": result["deleted"]})
