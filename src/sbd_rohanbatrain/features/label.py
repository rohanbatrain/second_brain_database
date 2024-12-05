import logging
from sbd_rohanbatrain.database.db import labels_collection
from datetime import datetime
from bson import ObjectId

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def add_label(name, color, description=""):
    """
    Adds a new label to the database.

    Parameters:
    name (str): The name of the label.
    color (str): The color of the label.
    description (str, optional): A description of the label. Defaults to an empty string.

    Returns:
    str: The ID of the inserted label, or None if a label with the same name already exists.
    """
    # Check if a label with the same name already exists
    existing_label = labels_collection.find_one({"name": name})
    if existing_label:
        logger.warning(f"Label creation failed: A label with the name '{name}' already exists.")
        return None  # Return None or raise an error depending on your use case
    
    label = {
        "name": name,
        "color": color,
        "description": description,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_active": True,
        "priority": "low",
        "category": "N/A"
    }
    
    result = labels_collection.insert_one(label)
    label_id = str(result.inserted_id)

    # Log label creation
    logger.info(f"Label created: {label_id} - Name: {name}, Color: {color}")
    
    return label_id


def update_label_name(label_name, new_name):
    """
    Updates the name of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_name (str): The new name for the label.
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"name": new_name, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    if result.modified_count > 0:
        logger.info(f"Label name updated to '{new_name}' for label '{label_name}'.")
    else:
        logger.warning(f"Label name update failed for label '{label_name}' (no changes made).")


def update_label_color(label_name, new_color):
    """
    Updates the color of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_color (str): The new color for the label.
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"color": new_color, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    if result.modified_count > 0:
        logger.info(f"Label color updated to '{new_color}' for label '{label_name}'.")
    else:
        logger.warning(f"Label color update failed for label '{label_name}' (no changes made).")


def update_label_description(label_name, new_description):
    """
    Updates the description of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_description (str): The new description for the label.
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"description": new_description, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    if result.modified_count > 0:
        logger.info(f"Label description updated to '{new_description}' for label '{label_name}'.")
    else:
        logger.warning(f"Label description update failed for label '{label_name}' (no changes made).")


def update_label_priority(label_name, new_priority):
    """
    Updates the priority of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_priority (str): The new priority for the label (e.g., "low", "medium", "high").
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"priority": new_priority, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    if result.modified_count > 0:
        logger.info(f"Label priority updated to '{new_priority}' for label '{label_name}'.")
    else:
        logger.warning(f"Label priority update failed for label '{label_name}' (no changes made).")


def update_label_category(label_name, new_category):
    """
    Updates the category of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_category (str): The new category for the label.
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"category": new_category, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    if result.modified_count > 0:
        logger.info(f"Label category updated to '{new_category}' for label '{label_name}'.")
    else:
        logger.warning(f"Label category update failed for label '{label_name}' (no changes made).")


def update_label_active_status(label_name, is_active):
    """
    Updates the active status of the label.

    Parameters:
    label_name (str): The name of the label to update.
    is_active (bool): The new active status for the label.
    """
    result = labels_collection.update_one(
        {"name": label_name},
        {"$set": {"is_active": is_active, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )

    status = "active" if is_active else "inactive"
    
    if result.modified_count > 0:
        logger.info(f"Label status updated to {status} for label '{label_name}'.")
    else:
        logger.warning(f"Label status update failed for label '{label_name}' (no changes made).")



def view_labels():
    """
    Retrieves and displays all labels from the database.

    Returns:
    list: A list of labels from the database.
    """
    labels = labels_collection.find()
    label_list = [{"name": label["name"], "color": label["color"]} for label in labels]
    
    # Log the viewing of labels
    logger.info(f"Retrieved {len(label_list)} labels from the database.")
    
    return label_list

def delete_label(label_id):
    """
    Deletes a label from the database by its ID.

    Parameters:
    label_id (str): The unique identifier of the label to be deleted.

    Returns:
    int: The number of labels deleted.
    """
    result = labels_collection.delete_one({"_id": ObjectId(label_id)})
    deleted_count = result.deleted_count

    # Log label deletion
    if deleted_count > 0:
        logger.info(f"Label deleted: {label_id}")
    else:
        logger.warning(f"Label deletion failed for ID: {label_id} (label not found)")

    return deleted_count