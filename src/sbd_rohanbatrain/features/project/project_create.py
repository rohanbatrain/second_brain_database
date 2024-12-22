from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId

def add_project(name, description, priority="low"):
    """
    Adds a new project to the database with a creation date.

    Args:
        name (str): The name of the project.
        description (str): A brief description of the project.
        priority (str): The priority of the project (default: "low").

    Returns:
        str: The ID of the newly added project.
    """
    creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   
    project = {
        "name": name,
        "description": description,
        "creation_date": creation_date,
        "priority": priority
    }

    try:
        result = projects_collection.insert_one(project)
        return str(result.inserted_id)
    except Exception as e:
        raise RuntimeError(f"An error occurred while adding the project: {str(e)}")


def view_projects():
    """
    Fetches all projects from the database.

    Returns:
        list: A list of dictionaries, each representing a project.
    """
    try:
        projects = list(projects_collection.find())
        return projects
    except Exception as e:
        raise RuntimeError(f"An error occurred while fetching the projects: {str(e)}")

