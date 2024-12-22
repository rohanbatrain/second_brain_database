


# **Delete** function to delete water intake entry by ID
def delete_water_intake_entry(entry_id):
    """
    Deletes a water intake entry by its ID.
    """
    try:
        # Convert entry_id to ObjectId
        entry_id_obj = ObjectId(entry_id)

        # Delete the water intake entry by ID
        result = water_intake_collection.delete_one({"_id": entry_id_obj})
        
        if result.deleted_count > 0:
            return f"Water intake entry with ID {entry_id} deleted successfully."
        else:
            return f"No entry found with ID {entry_id} to delete."
    except Exception as e:
        return f"An error occurred: {e}"