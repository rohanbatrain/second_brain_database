
def delete_entry(entry_id):
    """
    Delete an entry from MongoDB by its unique ID.

    :param entry_id: The unique ID of the entry to delete.
    :return: True if the entry was successfully deleted, False otherwise.
    :raises ValueError: If the entry with the given ID does not exist.
    :raises RuntimeError: If an error occurs during the deletion process.
    """
    try:
        # Attempt to delete the entry
        result = collection.delete_one({"_id": ObjectId(entry_id)})

        if result.deleted_count == 0:
            raise ValueError(f"No entry found with ID {entry_id}")

        return True

    except Exception as e:
        raise RuntimeError(f"An error occurred while deleting the entry: {str(e)}")
