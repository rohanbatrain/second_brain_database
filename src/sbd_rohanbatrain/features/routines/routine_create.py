from pymongo import MongoClient
from bson import ObjectId
from sbd_rohanbatrain.database.db import routine_collection

# Create a new routine entry
def create_routine_entry(task_id, frequency):
    """
    Creates a routine entry for the given task with the specified frequency.

    Args:
        task_id (str): The ID of the task to associate with the routine.
        frequency (str): The frequency of the routine (e.g., "daily", "weekly", etc.)

    Returns:
        str: The ID of the created routine entry
    """
    try:
        routine_entry = {
            "task_id": ObjectId(task_id),
            "frequency": frequency,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        # Insert into the routine collection
        result = routine_collection.insert_one(routine_entry)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating routine entry: {e}")
        return None

# Example usage
if __name__ == "__main__":
    result = create_routine_entry(routine_collection, "daily", "63f5b5bcf23b9c3f9c4d1234")
    print(result)