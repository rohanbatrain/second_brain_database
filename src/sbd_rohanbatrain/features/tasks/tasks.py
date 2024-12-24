from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import tasks_collection, routine_collection
from sbd_rohanbatrain.features.routines.routine_create import create_routine_entry

def create_task(title, description, due_date, priority, parent_task=None, dependencies=[], task_reference_id=None, is_routine=False, frequency=None):
    """
    Creates a new task and associates it with a routine if specified.

    Args:
        title (str): The title or name of the task.
        description (str): A brief description of the task.
        due_date (datetime): The due date of the task.
        priority (int): The priority of the task on a scale from 1 (lowest) to 5 (highest).
        parent_task (str, optional): The ID of the parent task if this task is a subtask. Default is None.
        dependencies (list, optional): A list of task IDs that are dependencies for this task. Default is an empty list.
        task_reference_id (dict, optional): A dictionary containing references to related entities such as habit, routine, or goal. Default is None.
        is_routine (bool, optional): A flag to indicate whether the task is part of a routine. Default is False.
        frequency (str, optional): The frequency of the routine task (e.g., "daily", "weekly"). Only required if `is_routine` is True.

    Returns:
        str: The ID of the created task, or None if there was an error.
    
    This function creates a new task document in the task collection, and if the task is associated
    with a routine, a routine entry is created and linked to the task. The task's reference ID is stored
    as a dictionary with separate fields for habit, routine, and goal.
    """
    try:
        task_reference = {
            "habit": [],
            "routine": [],
            "goal": []
        }

        # If the task is a routine, create a routine entry and update the task_reference_id
        if is_routine and frequency:
            routine_id = create_routine_entry(task_id=None, frequency=frequency)  # Create routine entry without task initially
            if routine_id:
                task_reference["routine"].append(ObjectId(routine_id))  # Add routine reference

        task = {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "is_completed": False,
            "parent_task": parent_task,
            "dependencies": [ObjectId(dep) for dep in dependencies],
            "task_reference_id": task_reference,  # Store task_reference_id as a dictionary
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        # Insert the task into the collection
        result = tasks_collection.insert_one(task)
        task_id = str(result.inserted_id)

        # If it was a routine task, update the task_reference_id for the created task
        if is_routine and frequency:
            tasks_collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"task_reference_id.routine": [ObjectId(routine_id)]}}  # Link routine to task
            )

        return task_id
    except Exception as e:
        print(f"Error creating task: {e}")
        return None


def create_routine_task(title, description, due_date, priority, parent_task=None, dependencies=[], task_reference_id=None, frequency=None):
    """
    Creates a task specifically designed as a routine task with a specified frequency.

    Args:
        title (str): The title or name of the task.
        description (str): A brief description of the task.
        due_date (datetime): The due date of the task.
        priority (int): The priority of the task on a scale from 1 (lowest) to 5 (highest).
        parent_task (str, optional): The ID of the parent task if this task is a subtask. Default is None.
        dependencies (list, optional): A list of task IDs that are dependencies for this task. Default is an empty list.
        task_reference_id (dict, optional): A dictionary containing references to related entities such as habit, routine, or goal. Default is None.
        frequency (str, optional): The frequency of the routine task (e.g., "daily", "weekly"). Required to indicate the task is routine.

    Returns:
        str: The ID of the created routine task, or None if there was an error.
    
    This helper function calls the `create_task` function with `is_routine=True` to create a task
    specifically linked to a routine with a specified frequency.
    """
    return create_task(
        title, description, due_date, priority, parent_task, dependencies, task_reference_id, is_routine=True, frequency=frequency
    )
