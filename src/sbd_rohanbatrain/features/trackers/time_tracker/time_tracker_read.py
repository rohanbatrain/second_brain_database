from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from sbd_rohanbatrain.database.db import time_tracker_collection

# Function to retrieve a time entry by ID (Read)
def get_time_entry(time_entry_id):
    """
    Retrieve a time entry by its ID.
    """
    time_entry = time_tracker_collection.find_one({"_id": ObjectId(time_entry_id)})
    
    if time_entry:
        return time_entry
    return None

# Function to list all time entries (Read)
def list_time_entries():
    """
    List all time entries from the database.
    """
    time_entries = time_tracker_collection.find()
    return [entry for entry in time_entries]