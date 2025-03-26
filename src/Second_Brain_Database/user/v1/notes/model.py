from Second_Brain_Database.database import db
from bson import ObjectId
from datetime import datetime

# Initialize the notes collection
notes_collection = db["notes"]

# Function to insert a new note
def create_note(data):
    note_entry = {
        "username": data.get("username"),
        "title": data.get("title") or "Untitled", 
        "content": data.get("content"),
        "timestamp": datetime.now(),
    }
    result = notes_collection.insert_one(note_entry)
    return str(result.inserted_id)

# Function to get all notes by user
def get_all_notes_by_user(username):
    return list(notes_collection.find({"username": username}))

# Function to get a single note by ID
def get_note_by_id(note_id):
    return notes_collection.find_one({"_id": ObjectId(note_id)})

# Function to update a note
def update_note(note_id, update_data):
    if "timestamp" in update_data:
        update_data["timestamp"] = datetime.now()

    result = notes_collection.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": update_data},
    )
    return result.matched_count > 0

# Function to delete a note
def delete_note(note_id):
    result = notes_collection.delete_one({"_id": ObjectId(note_id)})
    return result.deleted_count > 0
