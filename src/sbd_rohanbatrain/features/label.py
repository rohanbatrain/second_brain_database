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
    str: The ID of the inserted label.
    """
    label = {
        "name": name,
        "color": color,
        "description": description,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_active": True,
        "priority": "low",
        # "category": "task"
    }
    
    result = labels_collection.insert_one(label)
    label_id = str(result.inserted_id)

    # Log label creation
    logger.info(f"Label created: {label_id} - Name: {name}, Color: {color}")
    
    return label_id

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

def print_label_added(label_id):
    """
    Prints a message when a label is added.

    Parameters:
    label_id (str): The ID of the label added.

    Returns:
    None
    """
    logger.info(f"Label added with ID: {label_id}")
    print(f"Label added with ID: {label_id}")

def print_labels_viewed(labels):
    """
    Prints the labels retrieved from the database.

    Parameters:
    labels (list): The list of labels to print.

    Returns:
    None
    """
    for label in labels:
        print(f"Name: {label['name']}, Color: {label['color']}")
    
    logger.info(f"Printed {len(labels)} labels.")

def print_label_deleted(deleted_count):
    """
    Prints a message when labels are deleted.

    Parameters:
    deleted_count (int): The number of labels deleted.

    Returns:
    None
    """
    print(f"Deleted {deleted_count} label(s)")
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} label(s)")
    else:
        logger.warning("No labels were deleted.")
