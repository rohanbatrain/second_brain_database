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


# Create a new person entry
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