from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId

def add_project(name: str, description: str) -> str:
    """
    Adds a new project to the database with a creation date.

    Args:
        name (str): The name of the project.
        description (str): A brief description of the project.

    Returns:
        str: The ID of the newly added project.
    """
    creation_date = datetime.now().strftime("%Y-%m-%d")  # Current date
    creation_time = datetime.now().strftime("%H:%M:%S")  # Current time
    project = {
        "name": name,
        "description": description,
        "creation_date": creation_date,  # Adding the creation date field
        "creation_time": creation_time  # Adding the creation time field
    }

    result = projects_collection.insert_one(project)
    project_id = str(result.inserted_id)
    return project_id


def view_projects():
    """
    Fetches all projects from the database.

    Returns:
        list: A list of dictionaries, each representing a project.
    """
    projects = list(projects_collection.find())
    return projects


def delete_project(project_id):
    """
    Deletes a project from the database by its ID.

    Args:
        project_id (str): The unique ID of the project to be deleted.

    Returns:
        int: The number of projects deleted (1 if successful, 0 otherwise).
    """
    result = projects_collection.delete_one({"_id": ObjectId(project_id)})
    return result.deleted_count
