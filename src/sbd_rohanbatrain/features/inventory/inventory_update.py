from datetime import datetime
from sbd_rohanbatrain.database.db import inventory_collection
from bson import ObjectId

def update_inventory_item(item_id, item_name=None, item_type=None, date_modified=None):
    """
    Updates an existing item in the MongoDB inventory collection.
    
    Parameters:
    - item_id (str): The unique identifier of the item to be updated.
    - item_name (str, optional): The new name of the item (e.g., "Updated Router").
    - item_type (str, optional): The new type of the item (e.g., "Updated Device").
    - date_modified (str, optional): The date and time the item was last modified (default: current datetime, format: YYYY-MM-DD HH:MM:SS).
    
    Returns:
    - bool: `True` if the update was successful, `False` if no changes were made or the item was not found.
    """
    
    if not item_id:
        raise ValueError("Item ID is required.")
    
    # Prepare the update fields
    update_fields = {}
    
    if item_name:
        update_fields["item_name"] = item_name
    if item_type:
        update_fields["item_type"] = item_type
    if date_modified:
        update_fields["modified_at"] = date_modified
    else:
        # Use current date and time if not provided
        update_fields["modified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not update_fields:
        print("No fields to update.")
        return False
    
    # Update the item in the collection
    result = inventory_collection.update_one(
        {"_id": ObjectId(item_id)}, 
        {"$set": update_fields}
    )
    
    if result.matched_count > 0:
        print(f"Item with ID {item_id} has been updated.")
        return True
    else:
        print(f"Item with ID {item_id} not found.")
        return False