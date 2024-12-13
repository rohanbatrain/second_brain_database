from datetime import datetime
from sbd_rohanbatrain.database.db import sleep_collection

collection = sleep_collection

# Ensure that date defaults to today's date if not provided
def check_entry(date=None):
    """
    Checks if a sleep log entry exists for the given date.

    If no entry exists, a new entry is created.

    Args:
        date (str, optional): The date to check in "YYYY-MM-DD" format. Defaults to today's date.

    Returns:
        int: Returns 0 if a new entry is created, 1 if an entry already exists.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    if not collection.find_one({"date": date}):
        create_entry(date)
        return 0
    else:
        return 1


def create_entry(date=None):
    """
    Creates a new sleep log entry for the specified date.

    Args:
        date (str, optional): The date for the new entry in "YYYY-MM-DD" format. Defaults to today.

    Returns:
        dict: The created entry.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    entry = {
        "date": date,
        "bedtime": "",
        "wake_up_time": "",
        "total_sleep_time": "",
        "sleep_cycles": 0,
        "sleep_rating": 0,
        "dreams": "",
        "awakenings": [],
        "general_quality": "",
        "room_temperature": 0.0,
        "noise_level": "",
        "light_exposure": "",
        "sleep_position": "",
        "bedding_comfort": "",
        "pillow_type": "",
        "mattress_type": "",
        "sleeping_clothing": "",
        "sleep_aid_used": "",
        "sleep_temperature_preference": ""
    }
    collection.insert_one(entry)
    return entry
