
# **Read** function to get water intake entry by ID
def get_water_intake_entry_by_id(entry_id):
    """
    Retrieves a specific water intake entry by its ID.
    """
    try:
        # Convert entry_id to ObjectId
        entry_id_obj = ObjectId(entry_id)

        # Retrieve the water intake entry by ID
        entry = water_intake_collection.find_one({"_id": entry_id_obj})
        
        if entry:
            return entry  # Return the found entry
        else:
            return f"No water intake entry found with ID: {entry_id}"  # No entry found for the given ID
    except Exception as e:
        return f"An error occurred: {e}"  # Error handling