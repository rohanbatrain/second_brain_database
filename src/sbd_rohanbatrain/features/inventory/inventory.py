from datetime import datetime
from sbd_rohanbatrain.database.db import inventory_collection



def add_new_item_to_inventory(item_name, item_type, date_created=None, time_created=None, date_modified=None, time_modified=None):
    """
    Adds a new item to the MongoDB inventory collection with separate date and time fields.
    
    Parameters:
    - item_name (str): Name of the item (e.g., "Router", "Pan").
    - item_type (str): Type of the item (e.g., "Device", "Kitchen Supply").
    - date_created (str, optional): Date the item was created (default: today, format: YYYY-MM-DD).
    - time_created (str, optional): Time the item was created (default: now, format: HH:MM:SS).
    - date_modified (str, optional): Date the item was last modified (default: today, format: YYYY-MM-DD).
    - time_modified (str, optional): Time the item was last modified (default: now, format: HH:MM:SS).
    """
    if not item_name:
        raise ValueError("Item name is required.")
    if not item_type:
        raise ValueError("Item type is required.")
    
    # Use current date and time if not provided
    now = datetime.now()
    date_created = date_created or now.strftime("%Y-%m-%d")
    time_created = time_created or now.strftime("%H:%M:%S")
    date_modified = date_modified or date_created
    time_modified = time_modified or time_created

    # Prepare the document to insert
    item_document = {
        "item_name": item_name,
        "item_type": item_type,
        "date_created": date_created,
        "time_created": time_created,
        "date_modified": date_modified,
        "time_modified": time_modified,
    }

    # Insert the document into the MongoDB collection
    result = inventory_collection.insert_one(item_document)
    print(f"Item added successfully with ID: {result.inserted_id}")

# Example usage
add_new_item_to_inventory("Router", "Device")
add_new_item_to_inventory("Pan", "Kitchen Supply")

