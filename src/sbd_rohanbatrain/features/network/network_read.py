
def read_entry(entry_id):
    """
    Read the entry of a person based on their unique ID.

    :param entry_id: The unique ID of the person.
    :return: A dictionary containing the person's details, or raises an error if not found.
    """
    try:
        person = collection.find_one({"_id": ObjectId(entry_id)})
        
        if not person:
            raise ValueError(f"No person found with ID {entry_id}")

        return person

    except Exception as e:
        raise RuntimeError(f"An error occurred while reading the entry: {str(e)}")

