from bson import ObjectId
from sbd_rohanbatrain.database.db import goals_collection

def read_goal(goal_id):
    """
    Fetches a goal document by its unique identifier.

    Args:
        goal_id (ObjectId): The unique identifier of the goal to fetch.

    Returns:
        dict: The goal document if found, otherwise None.

    """
    try:
        goal = goals_collection.find_one({"_id": goal_id})
        return goal
    except Exception as e:
        print(f"An error occurred: {e}")
        return None