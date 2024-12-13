from sbd_rohanbatrain.database.db import sleep_collection

collection = sleep_collection

def delete_entry_by_id(id):
    """
    Deletes a sleep log entry by its unique id.

    Args:
        id (str): The unique identifier of the entry to be deleted.

    Returns:
        str: Message indicating success or failure.
    """
    result = collection.delete_one({"_id": id})
    if result.deleted_count > 0:
        return "Entry deleted successfully."
    else:
        return "Entry with the given id not found."
