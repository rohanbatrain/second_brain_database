from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from sbd_rohanbatrain.database.db import time_tracker_collection

# Function to update a time entry (Update)
def update_time_entry(time_entry_id, entry=None, project_id=None, task_id=None, label_ids=None, description=None):
    """
    Update the details of an existing time entry.
    """
    update_fields = {}
    
    if entry:
        update_fields["entry"] = entry
    if project_id:
        update_fields["project_id"] = project_id
    if task_id:
        update_fields["task_id"] = task_id
    if label_ids:
        update_fields["label_ids"] = label_ids
    if description:
        update_fields["description"] = description
    
    result = time_tracker_collection.update_one(
        {"_id": ObjectId(time_entry_id)},
        {"$set": update_fields}
    )
    
    if result.matched_count > 0:
        return time_entry_id
    return None
