from typing import Dict, List, Optional
from datetime import datetime
import logging
from sbd_rohanbatrain.database.db import network_collection

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the default logging level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sbd.logs"),  # Log to a file
        logging.StreamHandler()  # Also log to the console
    ]
)

collection = network_collection

# Helper function to check for name conflicts
def check_person_name_conflict(first_name: str, last_name: str) -> List[Dict]:
    """
    Helper function to check if a person with the given first and last name exists in the database.
    It returns the list of matching people or raises errors if no or multiple people are found.

    Args:
        first_name (str): First name of the person.
        last_name (str): Last name of the person.

    Returns:
        list: A list of people matching the first and last name.
    """
    people = find_person_by_name(first_name, last_name)

    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        raise ValueError(f"Multiple people found with name {first_name} {last_name}. Update aborted.")

    return people

# Creation Functions (cRUD)

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

def find_person_by_name(first_name: str, last_name: str) -> List[Dict]:
    """
    Helper function to find a person by first and last name.
    Returns a list of people matching the name.
    """
    return list(collection.find({"first_name": first_name, "last_name": last_name}))

def read_entry(first_name: str, last_name: str) -> Dict:
    """
    Read the entry of a person based on first name and last name.

    Args:
        first_name (str): The first name of the person to be retrieved.
        last_name (str): The last name of the person to be retrieved.

    Returns:
        dict: The found entry or a list of candidates if multiple people match the same name.
    """
    people = find_person_by_name(first_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {last_name}")
    
    if len(people) > 1:
        # If multiple people are found, return a list of candidates with their id and name
        return {"conflict": True, "candidates": [{"id": person["_id"], "name": f"{person['first_name']} {person['last_name']}"} for person in people]}
    
    # If exactly one person is found, return their details
    return people[0]

# Update Functions (CRuD)

def update_first_name(first_name: str, last_name: str, new_first_name: str) -> Dict:
    """
    Update the first name of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_first_name (str): The new first name to set.

    Returns:
        dict: The updated entry, or raises a ValueError if no matching person is found or other error occurs.
    """
    # Use the helper function to handle name conflict check
    people = check_person_name_conflict(first_name, last_name)
    person_to_update = people[0]

    # Proceed with updating the first name
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"first_name": new_first_name}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    
    if updated_entry:
        return updated_entry
    else:
        raise ValueError(f"Failed to update the first name of {first_name} {last_name}")

def update_last_name(first_name: str, last_name: str, new_last_name: str) -> Dict:
    """
    Update the last name of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_last_name (str): The new last name to set.

    Returns:
        dict: The updated entry, or raises a ValueError if no matching person is found or other error occurs.
    """
    # Use the helper function to handle name conflict check
    people = check_person_name_conflict(first_name, last_name)
    person_to_update = people[0]

    # Proceed with updating the last name
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"last_name": new_last_name}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    
    if updated_entry:
        return updated_entry
    else:
        raise ValueError(f"Failed to update the last name of {first_name} {last_name}")

def update_date_of_birth(first_name: str, last_name: str, new_dob: str) -> Dict:
    """
    Update the date of birth of a person.

    Args:
        first_name (str): The first name of the person to be updated.
        last_name (str): The last name of the person to be updated.
        new_dob (str): The new date of birth to set in 'YYYY-MM-DD' format.

    Returns:
        dict: The updated entry, or raises a ValueError if no matching person is found or other error occurs.
    """
    new_dob_datetime = datetime.strptime(new_dob, "%Y-%m-%d")

    # Use the helper function to handle name conflict check
    people = check_person_name_conflict(first_name, last_name)
    person_to_update = people[0]

    # Proceed with updating the date of birth
    result = collection.update_one(
        {"_id": person_to_update["_id"]},
        {"$set": {"date_of_birth": new_dob_datetime}}
    )

    updated_entry = collection.find_one({"_id": person_to_update["_id"]})
    
    if updated_entry:
        return updated_entry
    else:
        raise ValueError(f"Failed to update the date of birth for {first_name} {last_name}")
