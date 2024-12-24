from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from sbd_rohanbatrain.database.db import time_tracker_collection


# Function to start logging a time entry
def start_time_logging(entry, project_id=None, task_id=None, label_ids=None, description=None):
    """
    Start tracking time for an 'entry' (task/event).
    """
    time_entry = {
        "entry": entry,  # The task or event being tracked
        "project_id": project_id,
        "task_id": task_id,
        "start_time": datetime.now(),  # Current time when the task starts
        "end_time": None,              # Will be set later when stopped
        "label_ids": label_ids or [],  # Optional labels for categorization
        "description": description     # Optional description of the task/event
    }

    # Insert the time entry into the MongoDB collection
    result = time_tracker_collection.insert_one(time_entry)
    
    # Return only the inserted ID
    return str(result.inserted_id)

# Function to stop logging a time entry
def stop_time_logging(time_entry_id):
    """
    Stop tracking time for the given time entry.
    """
    # Find the time entry by its ID
    time_entry = time_tracker_collection.find_one({"_id": ObjectId(time_entry_id)})
    
    if not time_entry:
        return None  # Return None if the time entry was not found
    
    if time_entry["end_time"]:
        return None  # Return None if the time entry has already been stopped
    
    # Set the end time to the current time
    end_time = datetime.now()
    duration = (end_time - time_entry["start_time"]).total_seconds()  # Duration in seconds
    
    # Update the time entry with the end time and calculated duration
    update_fields = {
        "end_time": end_time,
        "duration": duration  # Duration in seconds
    }
    
    # Update the time entry in the database
    result = time_tracker_collection.update_one(
        {"_id": ObjectId(time_entry_id)},
        {"$set": update_fields}
    )
    
    if result.matched_count == 0:
        return None  # Return None if the time entry was not updated
    
    # Return the ID of the updated time entry
    return time_entry_id

# Example of starting a time entry
if __name__ == "__main__":
    # Example usage of start and stop logging
    start_result = start_time_logging(
        entry="Writing a report",  # The 'entry' represents the task or event
        project_id="project1",
        task_id="task1",
        label_ids=["label1", "label2"],
        description="Writing the final draft of the report"
    )
    print(start_result)  # Will print the time entry ID
    
    # Example usage of stopping the time entry (replace with actual time_entry_id)
    time_entry_id = start_result  # Replace this with the actual ID in a real use case
    stop_result = stop_time_logging(time_entry_id)
    print(stop_result)  # Will print the time entry ID if updated or None
