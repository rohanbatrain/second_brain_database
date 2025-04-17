from Second_Brain_Database.database import db
from bson import ObjectId
from datetime import datetime

# Initialize the notes collection
notes_collection = db["emotion_tracker"]
notes_db = db["notes"]  # Assuming a "notes" collection exists to fetch notes by IDs

# Function to fetch notes by their IDs
def fetch_notes_by_ids(note_ids):
    return list(notes_db.find({"_id": {"$in": [ObjectId(note_id) for note_id in note_ids]}}))

# Function to insert a new emotion tracking entry
def create_emotion(data):
    emotion_entry = {
        "username": data.get("username"),
        "emotion_felt": data.get("emotion_felt"),
        "emotion_intensity": data.get("emotion_intensity"),
        "note_ids": data.get("note_ids", []),
        "timestamp": datetime.now(),
    }
    result = notes_collection.insert_one(emotion_entry)
    return str(result.inserted_id)

# Function to get all emotion tracking entries by user
def get_all_emotions_by_user(username):
    emotions = list(notes_collection.find({"username": username}))
    for emotion in emotions:
        emotion["notes"] = fetch_notes_by_ids(emotion.get("note_ids", []))  # Resolve note_ids to notes
    return emotions

# Function to get a single emotion tracking entry by ID
def get_emotion_by_id(emotion_id):
    emotion = notes_collection.find_one({"_id": ObjectId(emotion_id)})
    if emotion:
        emotion["notes"] = fetch_notes_by_ids(emotion.get("note_ids", []))  # Resolve note_ids to notes
    return emotion

# Function to update an emotion tracking entry
def update_emotion(emotion_id, update_data):
    if "timestamp" in update_data:
        update_data["timestamp"] = datetime.now()

    result = notes_collection.update_one(
        {"_id": ObjectId(emotion_id)},
        {"$set": update_data},
    )
    return result.matched_count > 0

# Function to delete an emotion tracking entry
def delete_emotion(emotion_id):
    result = notes_collection.delete_one(
        {"_id": ObjectId(emotion_id)}
    )
    return result.deleted_count > 0

# Function to append a note ID to an emotion's note_ids array
def append_note_to_emotion(emotion_id, note_id):
    """
    Appends a note ID to the note_ids array of a specific emotion entry.

    Args:
        emotion_id (str): The ID of the emotion entry.
        note_id (str): The ID of the note to append.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    result = notes_collection.update_one(
        {"_id": ObjectId(emotion_id)},
        {"$push": {"note_ids": note_id}}
    )
    return result.modified_count > 0
