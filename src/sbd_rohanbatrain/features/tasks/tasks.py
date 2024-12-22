from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import tasks_collection


# Create a new task
def create_task(title, description, due_date, priority, parent_task=None, dependencies=[], task_reference_id=None):
    """
    Creates a new task in the collection.

    Args:
        title (str): Title of the task
        description (str): Description of the task
        due_date (datetime): Due date of the task
        priority (int): Task priority (1-5 scale)
        parent_task (str): Parent task ID if this is a subtask (default: None)
        dependencies (list): List of task dependencies (default: empty list)
        task_reference_id (str): Reference ID for the related task/entity (e.g., habit, project, etc.) (default: None)

    Returns:
        str: ID of the created task
    """
    try:
        task = {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "is_completed": False,
            "parent_task": parent_task,
            "dependencies": [ObjectId(dep) for dep in dependencies],
            "task_reference_id": ObjectId(task_reference_id) if task_reference_id else None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        result = tasks_collection.insert_one(task)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating task: {e}")
        return None


# Get all tasks (optionally by completion status)
def get_all_tasks(is_completed=None):
    """
    Retrieves all tasks, optionally filtered by completion status.

    Args:
        is_completed (bool): Whether to filter tasks by completion status (default: None)

    Returns:
        list: List of tasks
    """
    try:
        if is_completed is None:
            return list(tasks_collection.find())
        return list(tasks_collection.find({"is_completed": is_completed}))
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []


# Get a task by ID
def get_task_by_id(task_id):
    """
    Retrieves a task by its ID.

    Args:
        task_id (str): ID of the task

    Returns:
        dict: The task document
    """
    try:
        return tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception as e:
        print(f"Error fetching task by ID: {e}")
        return None


# Update a task
def update_task(task_id, title=None, description=None, due_date=None, priority=None, is_completed=None, dependencies=None, task_reference_id=None):
    """
    Updates the specified task with new details.

    Args:
        task_id (str): ID of the task to update
        title (str): Updated title (default: None)
        description (str): Updated description (default: None)
        due_date (datetime): Updated due date (default: None)
        priority (int): Updated priority (default: None)
        is_completed (bool): Updated completion status (default: None)
        dependencies (list): Updated task dependencies (default: None)
        task_reference_id (str): Updated reference ID for related task/entity (default: None)

    Returns:
        bool: True if the update was successful
    """
    try:
        update_fields = {}
        if title: update_fields["title"] = title
        if description: update_fields["description"] = description
        if due_date: update_fields["due_date"] = due_date
        if priority: update_fields["priority"] = priority
        if is_completed is not None: update_fields["is_completed"] = is_completed
        if dependencies is not None: update_fields["dependencies"] = [ObjectId(dep) for dep in dependencies]
        if task_reference_id is not None: update_fields["task_reference_id"] = ObjectId(task_reference_id)

        if update_fields:
            result = tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": update_fields})
            return result.matched_count > 0
        return False
    except Exception as e:
        print(f"Error updating task: {e}")
        return False


# Delete a task
def delete_task(task_id):
    """
    Deletes a task by ID.

    Args:
        task_id (str): ID of the task to delete

    Returns:
        bool: True if the deletion was successful
    """
    try:
        result = tasks_collection.delete_one({"_id": ObjectId(task_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting task: {e}")
        return False


# Mark task as completed
def complete_task(task_id):
    """
    Marks the task as completed.

    Args:
        task_id (str): ID of the task to mark as completed

    Returns:
        bool: True if the task was successfully marked as completed
    """
    try:
        result = tasks_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"is_completed": True, "updated_at": datetime.now()}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error completing task: {e}")
        return False


# Get tasks by reference ID
def get_tasks_by_reference_id(reference_id):
    """
    Retrieves tasks by their reference ID.

    Args:
        reference_id (str): The reference ID associated with the task (e.g., habit or event)

    Returns:
        list: List of tasks related to the given reference ID
    """
    try:
        return list(tasks_collection.find({"task_reference_id": ObjectId(reference_id)}))
    except Exception as e:
        print(f"Error fetching tasks by reference ID: {e}")
        return []
