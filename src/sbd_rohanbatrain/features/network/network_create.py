from typing import Dict, List, Optional
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from sbd_rohanbatrain.database.db import network_collection

collection = network_collection

# Creation Functions (cRUD)
def create_entry(first_name, middle_name=None, last_name=None, date_of_birth=None, gender=None, date=None):
    """
    Create a new entry for a person and insert it into MongoDB. 
    Ensures a unique combination of first_name, middle_name, and last_name.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Use current date-time if none provided

    try:
        entry = {
            "creation_date": date,
            "last_updated": date,  # Set `last_updated` field to creation time initially
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "date_of_birth": datetime.strptime(date_of_birth, "%Y-%m-%d") if date_of_birth else None,
            "gender": gender,
        }

        # Insert entry into MongoDB
        collection.insert_one(entry)
        return entry

    except DuplicateKeyError:
        raise ValueError(f"An entry with the name {first_name} {middle_name or ''} {last_name} already exists.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while creating the entry: {str(e)}")

