from pymongo import MongoClient
from Second_Brain_Database.database import db
from bson import ObjectId
from datetime import datetime
from flask import jsonify

# Initialize the notes collection
notes_collection = db["notes"]

# Function to insert a new emotion tracking entry
def create_emotion(data):
    emotion_entry = {
        "username" : data.get("username"),
        "note_type": "emotion_tracking",  # Ensure note_type is always emotion_tracking
        "emotion_felt": data.get("emotion_felt"),
        "emotion_intensity": data.get("emotion_intensity"),
        "note": data.get("note"),
        "timestamp": datetime.now()
    }
    result = notes_collection.insert_one(emotion_entry)
    return str(result.inserted_id)

# Function to get all emotion tracking entries
def get_all_emotions():
    return list(notes_collection.find({"note_type": "emotion_tracking"}))

def get_all_emotions_by_user(username):
    return list(notes_collection.find({"note_type": "emotion_tracking" , "username": username}))

# Function to get a single emotion tracking entry by ID
def get_emotion_by_id(emotion_id):
    return notes_collection.find_one({"_id": ObjectId(emotion_id), "note_type": "emotion_tracking"})

# Function to update an emotion tracking entry
def update_emotion(emotion_id, update_data):
    if "timestamp" in update_data:
        update_data["timestamp"] = datetime.now()

    result = notes_collection.update_one(
        {"_id": ObjectId(emotion_id), "note_type": "emotion_tracking"},
        {"$set": update_data}
    )
    return result.matched_count > 0

# Function to delete an emotion tracking entry
def delete_emotion(emotion_id):
    result = notes_collection.delete_one({"_id": ObjectId(emotion_id), "note_type": "emotion_tracking"})
    return result.deleted_count > 0


