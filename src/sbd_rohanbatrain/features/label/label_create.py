from datetime import datetime
from sbd_rohanbatrain.database.db import labels_collection
from bson import ObjectId

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
    return str(result.inserted_id)