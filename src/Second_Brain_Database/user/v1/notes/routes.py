from flask import Blueprint, request, jsonify
from Second_Brain_Database.user.v1.notes.model import (
    create_note,
    delete_note,
    get_all_notes_by_user,
    get_note_by_id,
    update_note,
)
from Second_Brain_Database.utils.decorators.privileged import user_only

notes_bp = Blueprint("notes", __name__)

# Create a note
@notes_bp.route("/add", methods=["POST"])
@user_only
def add_note(user):
    data = request.json
    data["username"] = user.username
    note_id = create_note(data)
    return jsonify({"message": "Note created", "id": note_id}), 201

# Read all notes for the authenticated user
@notes_bp.route("/get", methods=["GET"])
@user_only
def fetch_all_notes(user):
    notes = get_all_notes_by_user(user.username)
    return jsonify(
        [
            {
                "_id": str(note["_id"]),
                "username": note.get("username", ""),
                "title": note.get("title", "Untitled"),
                "content": note.get("content", ""),
                "timestamp": note.get("timestamp", ""),
            }
            for note in notes
        ]
    )

# Read a single note by ID
@notes_bp.route("/get/<string:note_id>", methods=["GET"])
@user_only
def fetch_note_by_id(user, note_id):
    note = get_note_by_id(note_id)
    if note:
        return jsonify(
            {
                "_id": str(note["_id"]),
                "username": note["username"],
                "title": note["title"],
                "content": note["content"],
                "timestamp": note["timestamp"],
            }
        )
    return jsonify({"error": "Note not found"}), 404

# Read multiple notes by an array of IDs
@notes_bp.route("/get/batch", methods=["POST"])
@user_only
def fetch_notes_by_ids(user):
    note_ids = request.json.get("note_ids", [])
    notes = [get_note_by_id(note_id) for note_id in note_ids]
    result = [
        {
            "_id": str(note["_id"]),
            "username": note["username"],
            "title": note["title"],
            "content": note["content"],
            "timestamp": note["timestamp"],
        }
        for note in notes if note
    ]
    return jsonify(result)

# Update a note
@notes_bp.route("/update/<string:note_id>", methods=["PUT"])
@user_only
def modify_note(user, note_id):
    data = request.json
    updated = update_note(note_id, data)
    if updated:
        return jsonify({"message": "Note updated"})
    return jsonify({"error": "Note not found"}), 404

# Delete a note
@notes_bp.route("/delete/<string:note_id>", methods=["DELETE"])
@user_only
def remove_note(user, note_id):
    deleted = delete_note(note_id)
    if deleted:
        return jsonify({"message": "Note deleted"})
    return jsonify({"error": "Note not found"}), 404
