from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId

def read_project(project_id):
    """
    Fetches a project by its unique ID from the database.

    Args:
        project_id (str): The unique ID of the project.

    Returns:
        dict: The project details as a dictionary.

    Raises:
        ValueError: If no project with the given ID is found.
        RuntimeError: If an error occurs during the database query.
    """
    try:
        project = projects_collection.find_one({"_id": ObjectId(project_id)})
        
        if not project:
            raise ValueError(f"No project found with ID {project_id}")

        return project

    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the project: {str(e)}")
