from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from sbd_rohanbatrain.database.db import time_tracker_collection

# Function to delete a time entry (Delete)
def delete_time_entry(time_entry_id):
    """
    Delete a time entry by its ID.
    """
    result = time_tracker_collection.delete_one({"_id": ObjectId(time_entry_id)})
    
    if result.deleted_count > 0:
        return time_entry_id
    return None