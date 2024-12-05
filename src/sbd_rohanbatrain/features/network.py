from sbd_rohanbatrain.database.db import network_collection

collection = network_collection

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sbd.logs"),  # Log to a file
        logging.StreamHandler()  # Also log to the console
    ]
)


# Creation Functions (cRUD)

## Create a new person entry
def create_entry(first_name: str, last_name: str, date_of_birth: str, gender: str, date: Optional[str] = None) -> Dict:
    """
    Create a new entry for a person and insert it into MongoDB.

    Args:
        first_name (str): First name of the person.
        last_name (str): Last name of the person.
        date_of_birth (str): Date of birth in the format YYYY-MM-DD.
        gender (str): Gender of the person.
        date (str, optional): Date of the entry creation (default is current date if None).

    Returns:
        dict: The created entry.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # If no date is provided, use the current date-time
    
    entry = {
        "creation_date": date,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": datetime.strptime(date_of_birth, "%Y-%m-%d"),  # Convert date_of_birth to datetime object
        "gender": gender
    }

    # Insert entry into MongoDB
    collection.insert_one(entry)
    
    return entry

# Read Functions (CrUD)

def read_entry(first_name: str, last_name: str) -> Dict:
    """
    Read the entry of a person based on first name and last name.

    Args:
        first_name (str): The first name of the person to be retrieved.
        last_name (str): The last name of the person to be retrieved.

    Returns:
        dict: The found entry or a list of candidates if multiple people match the same name.
    """
    # Find the person(s) by name
    people = find_person_by_name(first_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        # If multiple people are found, return a list of candidates with their id and name
        return {"conflict": True, "candidates": [{"id": person["_id"], "name": f"{person['first_name']} {person['last_name']}"} for person in people]}
    
    # If exactly one person is found, return their details
    return people[0]

def find_person_by_name(first_name: str, last_name: str):
    """
    Helper function to find a person by first and last name.
    Returns a list of people matching the name.
    """
    return list(collection.find({"first_name": first_name, "last_name": last_name}))

# Update Functions (CRuD)

def update_first_name(first_name: str, last_name: str, new_first_name: str) -> Dict:
    """
    Update the first name of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_first_name (str): The new first name to set.

    Returns:
        dict: The updated entry.
    """
    # Find the person by name
    people = find_person_by_name(first_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        print(f"Multiple people found with name {first_name} {last_name}.")
        for person in people:
            print(f"ID: {person['_id']} - {person['first_name']} {person['last_name']}")
        person_id = input("Please enter the ID of the person to update: ")
        person_to_update = collection.find_one({"_id": person_id})
        if not person_to_update:
            raise ValueError(f"No person found with ID {person_id}")
    else:
        person_to_update = people[0]
    
    # Proceed with updating the first name
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"first_name": new_first_name}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    return updated_entry


def update_last_name(first_name: str, last_name: str, new_last_name: str) -> Dict:
    """
    Update the last name of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_last_name (str): The new last name to set.

    Returns:
        dict: The updated entry.
    """
    # Find the person by name
    people = find_person_by_name(first_name, last_name)

    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        print(f"Multiple people found with name {first_name} {last_name}.")
        for person in people:
            print(f"ID: {person['_id']} - {person['first_name']} {person['last_name']}")
        person_id = input("Please enter the ID of the person to update: ")
        person_to_update = collection.find_one({"_id": person_id})
        if not person_to_update:
            raise ValueError(f"No person found with ID {person_id}")
    else:
        person_to_update = people[0]
    
    # Proceed with updating the last name
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"last_name": new_last_name}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    return updated_entry


def update_date_of_birth(first_name: str, last_name: str, new_dob: str) -> Dict:
    """
    Update the date of birth of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_dob (str): The new date of birth to set in 'YYYY-MM-DD' format.

    Returns:
        dict: The updated entry.
    """
    new_dob_datetime = datetime.strptime(new_dob, "%Y-%m-%d")

    # Find the person by name
    people = find_person_by_name(first_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        print(f"Multiple people found with name {first_name} {last_name}.")
        for person in people:
            print(f"ID: {person['_id']} - {person['first_name']} {person['last_name']}")
        person_id = input("Please enter the ID of the person to update: ")
        person_to_update = collection.find_one({"_id": person_id})
        if not person_to_update:
            raise ValueError(f"No person found with ID {person_id}")
    else:
        person_to_update = people[0]
    
    # Proceed with updating the date of birth
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"date_of_birth": new_dob_datetime}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    return updated_entry


def update_gender(first_name: str, last_name: str, new_gender: str) -> Dict:
    """
    Update the gender of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_gender (str): The new gender to set.

    Returns:
        dict: The updated entry.
    """
    # Find the person by name
    people = find_person_by_name(first_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        print(f"Multiple people found with name {first_name} {last_name}.")
        for person in people:
            print(f"ID: {person['_id']} - {person['first_name']} {person['last_name']}")
        person_id = input("Please enter the ID of the person to update: ")
        person_to_update = collection.find_one({"_id": person_id})
        if not person_to_update:
            raise ValueError(f"No person found with ID {person_id}")
    else:
        person_to_update = people[0]
    
    # Proceed with updating the gender
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"gender": new_gender}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    return updated_entry


# Read Functions (CRUd)
def delete_entry(first_name: str, last_name: str) -> bool:
    """
    Deletes an entry for a person based on their first and last name.

    Args:
        first_name (str): First name of the person.
        last_name (str): Last name of the person.

    Returns:
        bool: True if the entry was deleted, False if no matching entry was found.
    """
    # Find the entry based on first and last name
    result = collection.delete_one({
        "first_name": first_name,
        "last_name": last_name
    })

    # Check if the deletion was successful
    if result.deleted_count > 0:
        logger.info(f"Entry deleted for {first_name} {last_name}.")
        return True
    else:
        logger.warning(f"No entry found for {first_name} {last_name}. Deletion failed.")
        return False