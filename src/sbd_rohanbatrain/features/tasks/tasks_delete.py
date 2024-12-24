

def delete_task(task_id):
    """
    Deletes a task by its unique ID.

    Args:
        task_id (str): The ID of the task to delete.

    Returns:
        bool: True if the task was successfully deleted, False otherwise.
    
    This function deletes a task document from the collection using the provided task ID.
    """
    try:
        result = tasks_collection.delete_one({"_id": ObjectId(task_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting task: {e}")
        return False