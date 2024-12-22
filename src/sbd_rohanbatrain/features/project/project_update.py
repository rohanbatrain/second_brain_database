from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId


def update_project(project_id, name=None, description=None, priority=None):
    """
    Updates an existing project in the database by its ID.

    Args:
        project_id (str): The unique ID of the project to be updated.
        name (str, optional): The new name for the project.
        description (str, optional): The new description for the project.
        priority (str, optional): The new priority of the project.

    Returns:
        bool: True if the project was updated, False if no fields were updated.
    
    Raises:
        ValueError: If no project with the given ID is found.
        RuntimeError: If an error occurs during the update process.
    """
    try:
        # Prepare the update fields dictionary
        update_fields = {}

        if name:
            update_fields["name"] = name
        if description:
            update_fields["description"] = description
        if priority:
            update_fields["priority"] = priority

        # Always update the `last_updated` field
        update_fields["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not update_fields:
            raise ValueError("No fields to update.")

        # Perform the update
        result = projects_collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_fields}
        )

        if result.matched_count > 0:
            return True
        else:
            raise ValueError(f"No project found with ID {project_id}")

    except Exception as e:
        raise RuntimeError(f"An error occurred while updating the project: {str(e)}")
