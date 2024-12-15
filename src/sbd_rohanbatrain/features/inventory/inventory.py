from datetime import datetime
from sbd_rohanbatrain.database.db import inventory_collection


def add_new_item_to_inventory(item_name, item_type, date_created=None, date_modified=None):
    """
    Adds a new item to the MongoDB inventory collection with combined date and time fields.
    
    Parameters:
    - item_name (str): Name of the item (e.g., "Router", "Pan").
    - item_type (str): Type of the item (e.g., "Device", "Kitchen Supply").
    - date_created (str, optional): Date and time the item was created (default: current datetime, format: YYYY-MM-DD HH:MM:SS).
    - date_modified (str, optional): Date and time the item was last modified (default: current datetime, format: YYYY-MM-DD HH:MM:SS).
    """
    
    if not item_name:
        raise ValueError("Item name is required.")
    if not item_type:
        raise ValueError("Item type is required.")
    
    # Use current date and time if not provided
    now = datetime.now()
    date_created = date_created or now.strftime("%Y-%m-%d %H:%M:%S")
    date_modified = date_modified or date_created

    # Prepare the document to insert
    item_document = {
        "item_name": item_name,
        "item_type": item_type,
        "created_at": date_created,
        "modified_at": date_modified,
    }

    # Insert the document into the MongoDB collection
    result = inventory_collection.insert_one(item_document)
    print(f"Item added successfully with ID: {result.inserted_id}")

# Example usage
# add_new_item_to_inventory("Pan", "Kitchen Supply")
