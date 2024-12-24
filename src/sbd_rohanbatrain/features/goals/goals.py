
def append_related_id(goal_id, related_type, related_id):
    """
    Appends a related ID to the specified array in the related_ids field of a goal document.

    Args:
        goal_id (str): The unique identifier (ObjectId) of the goal to be updated.
        related_type (str): The type of related ID to append ('routines', 'tasks', 'habits').
        related_id (str): The ID to be appended to the specified related_type array.

    Returns:
        str: A success or error message.

    Example:
        append_related_id("634f8bda24fdbb91cf72f98b", "tasks", "task123")
    """
    try:
        # Validate the related_type
        if related_type not in ["routines", "tasks", "habits"]:
            return "Error: related_type must be one of 'routines', 'tasks', or 'habits'."

        # Append the related_id to the specified array
        result = goals_collection.update_one(
            {"_id": ObjectId(goal_id)},
            {"$addToSet": {f"related_ids.{related_type}": related_id}}
        )

        # Check if the update was successful
        if result.matched_count > 0:
            return f"Successfully added {related_id} to {related_type} in goal {goal_id}."
        else:
            return f"Goal with ID {goal_id} not found."

    except Exception as e:
        return f"Error appending related ID: {str(e)}"


