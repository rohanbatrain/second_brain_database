from bson import ObjectId
from sbd_rohanbatrain.database.db import goals_collection

def delete_goal(goal_id):
    """
    Deletes a goal document from the MongoDB collection based on the provided goal_id.

    This function allows you to delete a specific goal from the database. The goal is identified 
    by its unique `goal_id`. If the goal is found, it will be removed from the collection; otherwise, 
    a message indicating the goal was not found will be displayed.

    Args:
        goal_id (str): The unique identifier (ObjectId) of the goal to be deleted.

    Returns:
        bool: `True` if the goal was successfully deleted, `False` if the goal was not found or an error occurred.

    Raises:
        Exception: If an error occurs during the deletion process, the exception is caught, an error message 
                   is printed, and the function returns `False`.

    Example:
        delete_goal("634f8bda24fdbb91cf72f98b")
        This will delete the goal with the ID "634f8bda24fdbb91cf72f98b" from the database.
    """
    try:
        # Delete the goal from the collection
        result = goals_collection.delete_one({"_id": ObjectId(goal_id)})

        if result.deleted_count > 0:
            print(f"Goal with ID {goal_id} has been deleted.")
            return True
        else:
            print(f"Goal with ID {goal_id} not found.")
            return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
