
def update_task(task_id, title=None, description=None, due_date=None, priority=None, is_completed=None, dependencies=None, task_reference_id=None):
    """
    Updates an existing task with new details.

    Args:
        task_id (str): The ID of the task to update.
        title (str, optional): The updated title for the task.
        description (str, optional): The updated description for the task.
        due_date (datetime, optional): The updated due date for the task.
        priority (int, optional): The updated priority for the task.
        is_completed (bool, optional): The updated completion status of the task.
        dependencies (list, optional): The updated list of task IDs that are dependencies for this task.
        task_reference_id (dict, optional): The updated dictionary of references to related entities.

    Returns:
        bool: True if the task was successfully updated, False otherwise.
    
    This function allows updating multiple fields of an existing task document in the collection, including
    its title, description, due date, priority, completion status, dependencies, and reference IDs.
    """
    try:
        update_fields = {}
        if title: update_fields["title"] = title
        if description: update_fields["description"] = description
        if due_date: update_fields["due_date"] = due_date
        if priority: update_fields["priority"] = priority
        if is_completed is not None: update_fields["is_completed"] = is_completed
        if dependencies is not None: update_fields["dependencies"] = [ObjectId(dep) for dep in dependencies]
        if task_reference_id is not None: update_fields["task_reference_id"] = task_reference_id

        if update_fields:
            result = tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": update_fields})
            return result.matched_count > 0
        return False
    except Exception as e:
        print(f"Error updating task: {e}")
        return False



def complete_task(task_id):
    """
    Marks a task as completed by setting its `is_completed` field to True.

    Args:
        task_id (str): The ID of the task to mark as completed.

    Returns:
        bool: True if the task was successfully marked as completed, False otherwise.
    
    This function updates the task document in the collection, marking it as completed and updating the timestamp.
    """
    try:
        result = tasks_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"is_completed": True, "updated_at": datetime.now()}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error completing task: {e}")
        return False


def append_to_task_reference(task_id, reference_type, reference_id):
    """
    Appends a reference ID to a specified field in the task's task_reference_id.

    Args:
        task_id (str): The ID of the task to update.
        reference_type (str): The type of reference to append ("habit", "routine", "goal").
        reference_id (str): The ID of the reference to append.

    Returns:
        bool: True if the reference was successfully appended, False otherwise.

    This function updates the task_reference_id in the task document by adding the specified reference
    ID to the appropriate array (habit, routine, or goal).
    """
    try:
        # Validate reference_type
        if reference_type not in ["habit", "routine", "goal"]:
            raise ValueError("Invalid reference type. Must be 'habit', 'routine', or 'goal'.")

        # Perform the update operation
        result = tasks_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$addToSet": {f"task_reference_id.{reference_type}": ObjectId(reference_id)}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error appending to task_reference: {e}")
        return False
