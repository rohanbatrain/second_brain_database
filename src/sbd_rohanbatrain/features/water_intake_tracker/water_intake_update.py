def update_water_intake_entry(entry_id, new_amount):
    """
    Updates the amount of a water intake entry by its ID.
    """
    try:
        # Convert entry_id to ObjectId
        entry_id_obj = ObjectId(entry_id)

        # Update the water intake entry with the new amount
        result = water_intake_collection.update_one(
            {"_id": entry_id_obj}, 
            {"$set": {"amount": new_amount, "timestamp": datetime.now()}}
        )
        
        if result.modified_count > 0:
            return f"Water intake entry with ID {entry_id} updated successfully."
        else:
            return f"No update made, entry with ID {entry_id} not found."
    except Exception as e:
        return f"An error occurred: {e}"