from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId


def delete_project(project_id):
    """
    Deletes a project from the database by its ID.

    Args:
        project_id (str): The unique ID of the project to be deleted.

    Returns:
        bool: True if the project was successfully deleted, False otherwise.
    """
    try:
        result = projects_collection.delete_one({"_id": ObjectId(project_id)})
        if result.deleted_count == 0:
            raise ValueError(f"No project found with ID {project_id}")
        return True
    except Exception as e:
        raise RuntimeError(f"An error occurred while deleting the project: {str(e)}")