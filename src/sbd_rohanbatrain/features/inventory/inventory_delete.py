from sbd_rohanbatrain.database.db import inventory_collection

def delete_item_by_id(item_id):
    """
    Deletes an item from the MongoDB inventory collection based on the item ID.
    
    Parameters:
    - item_id (str or ObjectId): The ID of the item to be deleted.
    
    Raises:
    - ValueError: If the item ID is not provided or if the item does not exist.
    """
    
    if not item_id:
        raise ValueError("Item ID is required.")
    
    # Try to delete the item using the item_id
    result = inventory_collection.delete_one({"_id": item_id})
    
    if result.deleted_count > 0:
        print(f"Item with ID '{item_id}' deleted successfully.")
    else:
        print(f"Item with ID '{item_id}' not found in the inventory.")

# Example usage:
# delete_item_by_id(ObjectId("your_item_id_here"))
