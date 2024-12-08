from datetime import datetime
from sbd_rohanbatrain.database.db import labels_collection
from bson import ObjectId

def update_label_name(label_id, new_name):
    """
    Updates the name of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    new_name (str): The new name for the label.
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"name": new_name, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_color(label_id, new_color):
    """
    Updates the color of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    new_color (str): The new color for the label.
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"color": new_color, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_description(label_id, new_description):
    """
    Updates the description of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    new_description (str): The new description for the label.
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"description": new_description, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_priority(label_id, new_priority):
    """
    Updates the priority of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    new_priority (str): The new priority for the label (e.g., "low", "medium", "high").
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"priority": new_priority, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_category(label_id, new_category):
    """
    Updates the category of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    new_category (str): The new category for the label.
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"category": new_category, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_active_status(label_id, is_active):
    """
    Updates the active status of the label.

    Parameters:
    label_id (str): The ID of the label to update.
    is_active (bool): The new active status for the label.
    """
    labels_collection.update_one(
        {"_id": ObjectId(label_id)},
        {"$set": {"is_active": is_active, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )
