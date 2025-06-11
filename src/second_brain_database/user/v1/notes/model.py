"""
model.py

Data access and business logic for notes in Second Brain Database.

Dependencies:
    - Second_Brain_Database.database
    - bson
    - datetime

Author: Rohan Batra
Date: 2025-06-11
"""

from datetime import datetime
from bson import ObjectId
from second_brain_database.database import db

# Initialize the notes collection
notes_collection = db["notes"]

# Function to insert a new note
def create_note(data):
    """
    Inserts a new note into the database.

    Args:
        data (dict): A dictionary containing the following keys:
            - username (str): The username of the note's owner.
            - title (str, optional): The title of the note. Defaults to "Untitled" if not provided.
            - content (str): The content of the note.

    Returns:
        str: The ID of the newly created note.
    """
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
    """
    Retrieves all notes for a specific user.

    Args:
        username (str): The username of the user whose notes are to be retrieved.

    Returns:
        list: A list of notes, where each note is represented as a dictionary.
    """
    return list(notes_collection.find({"username": username}))

# Function to get a single note by ID
def get_note_by_id(note_id):
    """
    Retrieves a single note by its ID.

    Args:
        note_id (str): The ID of the note to retrieve.

    Returns:
        dict or None: The note document if found, else None.
    """
    return notes_collection.find_one({"_id": ObjectId(note_id)})

# Function to update a note
def update_note(note_id, update_data):
    """
    Updates a note with the given data.

    Args:
        note_id (str): The ID of the note to update.
        update_data (dict): A dictionary containing the fields to update. 
            - Example keys: title (str), content (str), timestamp (datetime).

    Returns:
        bool: True if the note was updated, False otherwise.
    """
    if "timestamp" in update_data:
        update_data["timestamp"] = datetime.now()

    result = notes_collection.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": update_data},
    )
    return result.matched_count > 0

# Function to delete a note
def delete_note(note_id):
    """
    Deletes a note by its ID.

    Args:
        note_id (str): The ID of the note to delete.

    Returns:
        bool: True if the note was deleted, False otherwise.
    """
    result = notes_collection.delete_one({"_id": ObjectId(note_id)})
    return result.deleted_count > 0
