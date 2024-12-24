from pymongo import MongoClient
from datetime import datetime
from sbd_rohanbatrain.database.db import goals_collection

def create_goal(goal_type, goal_value, description, unit, frequency, related_ids=None, date_str=None):
    """
    Adds a new goal document to the MongoDB collection, including a progress field and related IDs.

    Args:
        goal_type (str): The type/category of the goal (e.g., 'fitness', 'productivity').
        goal_value (float): The target value of the goal (e.g., 100, 500).
        description (str): A brief description of the goal (e.g., 'Run 5 kilometers per day').
        unit (str): The unit of measurement for the goal value (e.g., 'kilometers', 'hours', 'steps').
        frequency (str): The frequency at which the goal should be achieved (e.g., 'daily', 'weekly').
        related_ids (dict, optional): Dictionary containing related IDs for routines, tasks, and habits.
        date_str (str, optional): The start date of the goal in 'YYYY-MM-DD' format.

    Returns:
        str: The inserted goal's unique identifier (ObjectId).

    """
    try:
        if date_str:
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            start_date = datetime.now().strftime('%Y-%m-%d')

        # Default related_ids to an empty dictionary if none is provided
        if related_ids is None:
            related_ids = {
                "routines": [],
                "tasks": [],
                "habits": []
            }

        goal = {
            "goal_type": goal_type,
            "start_date": start_date,
            "goal_value": goal_value,
            "description": description,
            "unit": unit,
            "frequency": frequency,
            "progress": 0,  # Add a progress field to track progress
            "related_ids": related_ids,  # Store related entity IDs
            "created_at": datetime.now()
        }

        result = goals_collection.insert_one(goal)
        return result.inserted_id

    except Exception as e:
        print(f"An error occurred: {e}")
        return None