from typing import Dict, List, Optional
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from sbd_rohanbatrain.database.db import network_collection

collection = network_collection

# Creation Functions (cRUD)
def create_entry(first_name: str, middle_name: Optional[str], last_name: str, date_of_birth: str, gender: str, date: Optional[str] = None) -> Dict:
    """
    Create a new entry for a person and insert it into MongoDB. Ensures unique combination of first_name, middle_name, last_name.
    Also sets the `last_updated` field to the current date-time.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # If no date is provided, use the current date-time
    
    entry = {
        "creation_date": date,
        "last_updated": date,  # Set the initial `last_updated` field to creation time
        "first_name": first_name,
        "middle_name": middle_name,  
        "last_name": last_name,
        "date_of_birth": datetime.strptime(date_of_birth, "%Y-%m-%d"),  # Convert date_of_birth to datetime object
        "gender": gender
    }

    try:
        # Insert entry into MongoDB
        collection.insert_one(entry)
        return entry
    except DuplicateKeyError:
        raise ValueError(f"An entry with the name {first_name} {middle_name or ''} {last_name} already exists in the database.")

# Read Functions (CrUD)
def read_entry(first_name: str, middle_name: Optional[str], last_name: str) -> Dict:
    """
    Read the entry of a person based on first name, middle name, and last name.
    """
    people = find_person_by_name(first_name, middle_name, last_name)
    
    if len(people) == 0:
        raise ValueError(f"No person found with name {first_name} {middle_name or ''} {last_name}")
    
    if len(people) > 1:
        # If multiple people are found, return a list of candidates with their id and name
        return {
            "conflict": True, 
            "candidates": [
                {"id": person["_id"], "name": f"{person['first_name']} {person.get('middle_name', '')} {person['last_name']}"}
                for person in people
            ]
        }
    
    # If exactly one person is found, return their details
    return people[0]

# Update Functions (CRuD)

def update_person_name(first_name: str, middle_name: Optional[str], last_name: str, update_data: Dict) -> Dict:
    """
    A generic update function to handle updates to the person's name or details.
    It also updates the `last_updated` field.
    """
    person = read_entry(first_name, middle_name, last_name)
    
    # Add or update the `last_updated` field in the update data
    update_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Set the current time for last_updated
    
    # Update person data
    update_result = collection.update_one(
        {"_id": person["_id"]},
        {"$set": update_data}
    )

    if update_result.modified_count == 0:
        raise ValueError(f"No changes made to {first_name} {middle_name or ''} {last_name}")

    # Return the updated entry
    return collection.find_one({"_id": person["_id"]})

def update_first_name(first_name: str, middle_name: Optional[str], last_name: str, new_first_name: str) -> Dict:
    """
    Update the first name of a person and modify the `last_updated` field.
    """
    return update_person_name(first_name, middle_name, last_name, {"first_name": new_first_name})

def update_last_name(first_name: str, middle_name: Optional[str], last_name: str, new_last_name: str) -> Dict:
    """
    Update the last name of a person and modify the `last_updated` field.
    """
    return update_person_name(first_name, middle_name, last_name, {"last_name": new_last_name})

def update_middle_name(first_name: str, middle_name: Optional[str], last_name: str, new_middle_name: str) -> Dict:
    """
    Update the middle name of a person and modify the `last_updated` field.
    """
    return update_person_name(first_name, middle_name, last_name, {"middle_name": new_middle_name})

def update_date_of_birth(first_name: str, middle_name: Optional[str], last_name: str, new_dob: str) -> Dict:
    """
    Update the date of birth of a person and modify the `last_updated` field.
    """
    new_dob_datetime = datetime.strptime(new_dob, "%Y-%m-%d")
    return update_person_name(first_name, middle_name, last_name, {"date_of_birth": new_dob_datetime})


# Function to ensure unique compound index on first_name, middle_name, and last_name
def create_unique_name_index():
    # List all indexes in the collection
    indexes = collection.list_indexes()
    
    # Define the index key for first_name, middle_name, and last_name
    unique_index = [("first_name", 1), ("middle_name", 1), ("last_name", 1)]
    
    # Check if the index already exists by inspecting the 'key' field in index specs
    for index in indexes:
        if index['key'] == dict(unique_index):
            return  # Index already exists, so no need to create it
    
    # If the index does not exist, create the unique index
    collection.create_index(unique_index, unique=True)

# Function calling
## Ensure the unique index is created when the script is first run
create_unique_name_index()