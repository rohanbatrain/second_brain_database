def get_all_tasks(is_completed=None):
    """
    Retrieves all tasks from the task collection, optionally filtered by completion status.

    Args:
        is_completed (bool, optional): A flag to filter tasks by completion status. If None, all tasks are returned. Default is None.

    Returns:
        list: A list of task documents that match the completion status filter (if provided).
    
    This function queries the task collection for all tasks, and optionally filters them based on whether
    they are marked as completed or not.
    """
    try:
        if is_completed is None:
            return list(tasks_collection.find())
        return list(tasks_collection.find({"is_completed": is_completed}))
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []




def get_task_by_id(task_id):
    """
    Retrieves a task by its unique ID.

    Args:
        task_id (str): The ID of the task to retrieve.

    Returns:
        dict: The task document corresponding to the given ID, or None if not found.
    
    This function queries the task collection to fetch a specific task based on its ID.
    """
    try:
        return tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception as e:
        print(f"Error fetching task by ID: {e}")
        return None

def get_tasks_by_reference_id(reference_id):
    """
    Retrieves tasks associated with a specific reference ID (e.g., routine, habit, goal).

    Args:
        reference_id (str): The reference ID to search for in the task reference fields.

    Returns:
        list: A list of task documents related to the given reference ID.
    
    This function queries the task collection for tasks whose reference ID includes a specified reference (e.g., routine, habit).
    """
    try:
        return list(tasks_collection.find({"task_reference_id.routine": ObjectId(reference_id)}))
    except Exception as e:
        print(f"Error fetching tasks by reference ID: {e}")
        return []
