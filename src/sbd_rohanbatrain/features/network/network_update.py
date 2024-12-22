
def update_entry(entry_id, first_name=None, middle_name=None, last_name=None, date_of_birth=None, gender=None):
    """
    Update an existing entry in MongoDB by its ID. 
    Allows updating any combination of fields while ensuring the `last_updated` field is updated.

    :param entry_id: The ID of the entry to update.
    :param first_name: Updated first name (default: None).
    :param middle_name: Updated middle name (default: None).
    :param last_name: Updated last name (default: None).
    :param date_of_birth: Updated date of birth in 'YYYY-MM-DD' format (default: None).
    :param gender: Updated gender (default: None).
    :return: True if the update was successful, False otherwise.
    :raises ValueError: If no fields are provided to update or if the date format is invalid.
    """
    # Prepare the update fields dictionary
    update_fields = {}

    if first_name:
        update_fields["first_name"] = first_name
    if middle_name:
        update_fields["middle_name"] = middle_name
    if last_name:
        update_fields["last_name"] = last_name
    if date_of_birth:
        try:
            update_fields["date_of_birth"] = datetime.strptime(date_of_birth, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date_of_birth format. Use 'YYYY-MM-DD'.")
    if gender:
        update_fields["gender"] = gender

    # Always update the `last_updated` field
    update_fields["last_updated"] = datetime.now()

    if not update_fields:
        raise ValueError("No fields to update.")

    try:
        # Perform the update
        result = collection.update_one(
            {"_id": ObjectId(entry_id)}, 
            {"$set": update_fields}
        )

        return result.matched_count > 0

    except Exception as e:
        raise RuntimeError(f"An error occurred while updating the entry: {str(e)}")
