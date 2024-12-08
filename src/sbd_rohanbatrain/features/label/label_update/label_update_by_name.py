
def update_label_name(label_name, new_name):
    """
    Updates the name of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_name (str): The new name for the label.
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"name": new_name, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_color(label_name, new_color):
    """
    Updates the color of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_color (str): The new color for the label.
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"color": new_color, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_description(label_name, new_description):
    """
    Updates the description of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_description (str): The new description for the label.
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"description": new_description, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_priority(label_name, new_priority):
    """
    Updates the priority of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_priority (str): The new priority for the label (e.g., "low", "medium", "high").
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"priority": new_priority, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_category(label_name, new_category):
    """
    Updates the category of the label.

    Parameters:
    label_name (str): The name of the label to update.
    new_category (str): The new category for the label.
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"category": new_category, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )


def update_label_active_status(label_name, is_active):
    """
    Updates the active status of the label.

    Parameters:
    label_name (str): The name of the label to update.
    is_active (bool): The new active status for the label.
    """
    labels_collection.update_one(
        {"name": label_name},
        {"$set": {"is_active": is_active, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    )
