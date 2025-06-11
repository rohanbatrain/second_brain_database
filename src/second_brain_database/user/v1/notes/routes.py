"""
routes.py

Flask routes for note management (CRUD) for authenticated users.

Dependencies:
    - Flask
    - Second_Brain_Database.user.v1.notes.model
    - Second_Brain_Database.utils.decorators.privileged
    - Second_Brain_Database.user.v1.emotion_tracker.model

Author: Rohan Batra
Date: 2025-06-11
"""

from flask import Blueprint, request, jsonify

from second_brain_database.user.v1.notes.model import (
    create_note,
    delete_note,
    get_all_notes_by_user,
    get_note_by_id,
    update_note,
)
from second_brain_database.utils.decorators.privileged import user_only
from second_brain_database.user.v1.emotion_tracker.model import (
    append_note_to_emotion,
)

notes_bp = Blueprint("notes", __name__)


# Create a note
@notes_bp.route("/basic/add", methods=["POST"])
@user_only
def add_note(user):
    """
    Creates a new note for the authenticated user.

    Request JSON:
        {
            "title": (str, optional) The title of the note. Defaults to "Untitled".
            "content": (str) The content of the note.
        }

    Returns:
        JSON: A success message with the ID of the created note.
    """
    data = request.json
    data["username"] = user.username
    note_id = create_note(data)
    return jsonify({"message": "Note created", "id": note_id}), 201


# Create a note for a specific emotion ID
@notes_bp.route("/basic/add/<string:emotion_id>", methods=["POST"])
@user_only
def add_note_with_emotion(user, emotion_id):
    """
    Creates a new note for the authenticated user associated with a specific emotion ID.

    Args:
        emotion_id (str): The ID of the emotion to associate with the note.

    Request JSON:
        {
            "title": (str, optional) The title of the note. Defaults to "Untitled".
            "content": (str) The content of the note.
        }

    Returns:
        JSON: A success message with the ID of the created note.
    """
    data = request.json
    data["username"] = user.username
    data["emotion_id"] = emotion_id
    note_id = create_note(data)

    # Append the new note ID to the emotion's note array
    append_note_to_emotion(emotion_id, note_id)

    return jsonify({"message": "Note created", "id": note_id}), 201


# Read all notes for the authenticated user
@notes_bp.route("/basic/get", methods=["GET"])
@user_only
def fetch_all_notes(user):
    """
    Retrieves all notes for the authenticated user.

    Returns:
        JSON: A list of notes, where each note contains:
            - _id (str): The ID of the note.
            - username (str): The username of the note's owner.
            - title (str): The title of the note.
            - content (str): The content of the note.
            - timestamp (datetime): The timestamp of the note.
    """
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
@notes_bp.route("/basic/get/<string:note_id>", methods=["GET"])
@user_only
def fetch_note_by_id(user, note_id):  # pylint: disable=unused-argument
    """
    Retrieves a single note by its ID for the authenticated user.

    Args:
        note_id (str): The ID of the note to retrieve.

    Returns:
        JSON: The note details if found, or an error message if not found.
    """
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
@notes_bp.route("/basic/get/batch", methods=["POST"])
@user_only
def fetch_notes_by_ids(user):  # pylint: disable=unused-argument
    """
    Retrieves multiple notes by their IDs for the authenticated user.

    Request JSON:
        {
            "note_ids": (list of str) The IDs of the notes to retrieve.
        }

    Returns:
        JSON: A list of notes, where each note contains:
            - _id (str): The ID of the note.
            - username (str): The username of the note's owner.
            - title (str): The title of the note.
            - content (str): The content of the note.
            - timestamp (datetime): The timestamp of the note.
    """
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
@notes_bp.route("/basic/update/<string:note_id>", methods=["PUT"])
@user_only
def modify_note(user, note_id):  # pylint: disable=unused-argument
    """
    Updates a note by its ID for the authenticated user.

    Args:
        note_id (str): The ID of the note to update.

    Request JSON:
        {
            "title": (str, optional) The new title of the note.
            "content": (str, optional) The new content of the note.
        }

    Returns:
        JSON: A success message if the note was updated, or an error message if not found.
    """
    data = request.json
    updated = update_note(note_id, data)
    if updated:
        return jsonify({"message": "Note updated"})
    return jsonify({"error": "Note not found"}), 404


# Delete a note
@notes_bp.route("/basic/delete/<string:note_id>", methods=["DELETE"])
@user_only
def remove_note(user, note_id):  # pylint: disable=unused-argument
    """
    Deletes a note by its ID for the authenticated user.

    Args:
        note_id (str): The ID of the note to delete.

    Returns:
        JSON: A success message if the note was deleted, or an error message if not found.
    """
    deleted = delete_note(note_id)
    if deleted:
        return jsonify({"message": "Note deleted"})
    return jsonify({"error": "Note not found"}), 404
