from bson import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import goals_collection

def update_goal(goal_id, goal_type=None, start_date=None, goal_value=None, 
                description=None, unit=None, frequency=None, progress=None):
    """
    Updates an existing goal document in the MongoDB collection.

    Args:
        goal_id (str): The unique identifier (ObjectId) of the goal to be updated.
        goal_type (str, optional): New type/category for the goal (e.g., 'fitness').
        start_date (str, optional): New start date in 'YYYY-MM-DD' format.
        goal_value (float, optional): New target value for the goal (e.g., 100, 500).
        description (str, optional): New description of the goal.
        unit (str, optional): New unit of measurement for the goal value.
        frequency (str, optional): New frequency of the goal (e.g., 'daily').
        progress (float, optional): New progress value to update.

    Returns:
        ObjectId or None: The updated goal's unique identifier (goal_id) if the update is successful, or None if it fails.

    Example:
        update_goal("634f8bda24fdbb91cf72f98b", goal_value=150, description="Updated description")
    """
    try:
        # Initialize dictionary for update fields
        update_fields = {}

        # Validate and add each field to the update dictionary
        if goal_type:
            update_fields["goal_type"] = goal_type
        if start_date:
            try:
                update_fields["start_date"] = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                return None
        if goal_value:
            if isinstance(goal_value, (int, float)) and goal_value > 0:
                update_fields["goal_value"] = goal_value
            else:
                return None
        if description:
            update_fields["description"] = description
        if unit:
            update_fields["unit"] = unit
        if frequency:
            update_fields["frequency"] = frequency
        if progress:
            if isinstance(progress, (int, float)) and progress >= 0:
                update_fields["progress"] = progress
            else:
                return None

        # Check if there are any valid fields to update
        if not update_fields:
            return None

        # Update the document in MongoDB
        result = goals_collection.update_one(
            {"_id": ObjectId(goal_id)},
            {"$set": update_fields}
        )

        # Return the goal ID if update is successful
        if result.matched_count > 0:
            return goal_id
        else:
            return None

    except Exception as e:
        return None


from bson import ObjectId
from sbd_rohanbatrain.database.db import goals_collection

def update_progress(goal_id, progress):
    """
    Updates the progress of an existing goal document in the MongoDB collection.

    Args:
        goal_id (str): The unique identifier (ObjectId) of the goal to be updated.
        progress (float): The new progress value (must be between 0 and 100).

    Returns:
        str: The goal ID if the update is successful, or an error message if it fails.

    Example:
        update_progress("634f8bda24fdbb91cf72f98b", 50)
    """
    try:
        # Validate the progress value
        if not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
            return "Error: Progress must be a number between 0 and 100."
        
        # Update the progress field in MongoDB
        result = goals_collection.update_one(
            {"_id": ObjectId(goal_id)},
            {"$set": {"progress": progress}}
        )

        # Check if the update was successful
        if result.matched_count > 0:
            return f"Goal {goal_id} progress updated to {progress}%."
        else:
            return f"Goal with ID {goal_id} not found."

    except Exception as e:
        return f"Error updating progress: {str(e)}"
