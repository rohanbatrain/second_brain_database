import datetime
from sbd_rohanbatrain.database.db import sleep_collection

collection = sleep_collection

def delete_entry_by_date(date=None):
    """
    Deletes a sleep log entry by its date.

    Args:
        date (str, optional): The date of the entry to be deleted in "YYYY-MM-DD" format.
                              Defaults to today's date if not provided.

    Returns:
        str: Message indicating success or failure.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    result = collection.delete_one({"date": date})
    if result.deleted_count > 0:
        return "Entry deleted successfully."
    else:
        return "Entry with the given date not found."
