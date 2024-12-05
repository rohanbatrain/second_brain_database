import logging
from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sbd.logs"),  # Log to a file
        logging.StreamHandler()  # Also log to the console
    ]
)

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
        "creation_time" : creation_time # Adding the creation time field
    }

    result = projects_collection.insert_one(project)
    project_id = str(result.inserted_id)
    logging.info(f"Project added with ID: {project_id}")
    return project_id


def view_projects():
    """
    Fetches all projects from the database.

    Returns:
        list: A list of dictionaries, each representing a project.
    """
    projects = list(projects_collection.find())
    if projects:
        logging.info(f"Fetched {len(projects)} project(s) from the database.")
    else:
        logging.warning("No projects found in the database.")
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
    if result.deleted_count > 0:
        logging.info(f"Project with ID {project_id} deleted successfully.")
    else:
        logging.error(f"Failed to delete project with ID {project_id}. Project not found.")
    return result.deleted_count


