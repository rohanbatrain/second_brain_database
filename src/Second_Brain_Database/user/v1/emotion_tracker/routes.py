from flask import Blueprint, request, jsonify
from Second_Brain_Database.user.v1.emotion_tracker.model import (
    create_emotion,
    delete_emotion,
    get_all_emotions_by_user,
    get_emotion_by_id,
    update_emotion,
)
from Second_Brain_Database.utils.decorators.privileged import user_only
from Second_Brain_Database.user.v1.notes.model import create_note
emotion_bp = Blueprint("emotion_tracker", __name__)


# Create an emotion entry
@emotion_bp.route("/add", methods=["POST"])
@user_only
def add_emotion(user):
    data = request.json
    data["username"] = user.username  # Ensure the correct username is stored
    note_data = {
        "username": data.get("username"),
        "title": "Emotion Log",
        "content": data["note"],
    }
    note_id = create_note(note_data)
    emotion_data = {
        "username": data.get("username"),
        "emotion_felt": data.get("emotion_felt"),
        "emotion_intensity": data.get("emotion_intensity"),
        "note_ids": [note_id],

    }
    emotion_id = create_emotion(emotion_data)
    return jsonify({"message": "Emotion entry created", "id": emotion_id}), 201


# Read all emotion tracking entries for the authenticated user
@emotion_bp.route("/get", methods=["GET"])
@user_only
def fetch_all_emotions(user):
    emotions = get_all_emotions_by_user(user.username)
    return jsonify(
        [
            {
                "_id": str(emotion["_id"]),
                "username": emotion["username"],
                "emotion_felt": emotion["emotion_felt"],
                "emotion_intensity": emotion["emotion_intensity"],
                "note_ids": emotion["note_ids"],
                "timestamp": emotion["timestamp"],
            }
            for emotion in emotions
        ]
    )


# Read a single emotion entry by ID
@emotion_bp.route("/get/<string:emotion_id>", methods=["GET"])
@user_only
def fetch_emotion(user, emotion_id):
    emotion = get_emotion_by_id(emotion_id)
    if emotion:
        return jsonify(
            {
                "_id": str(emotion["_id"]),
                "username": emotion["username"],
                "emotion_felt": emotion["emotion_felt"],
                "emotion_intensity": emotion["emotion_intensity"],
                "note_ids": emotion["note_ids"],
                "timestamp": emotion["timestamp"],
            }
        )
    return jsonify({"error": "Emotion entry not found"}), 404


# Update an emotion entry
@emotion_bp.route("/update/<string:emotion_id>", methods=["PUT"])
@user_only
def modify_emotion(user, emotion_id):
    data = request.json
    updated = update_emotion(emotion_id, data)
    if updated:
        return jsonify({"message": "Emotion entry updated"})
    return jsonify({"error": "Emotion entry not found"}), 404


# Delete an emotion entry
@emotion_bp.route("/delete/<string:emotion_id>", methods=["DELETE"])
@user_only
def remove_emotion(user, emotion_id):
    deleted = delete_emotion(emotion_id)
    if deleted:
        return jsonify({"message": "Emotion entry deleted"})
    return jsonify({"error": "Emotion entry not found"}), 404
