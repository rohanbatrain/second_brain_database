import logging
from datetime import datetime
from decimal import Decimal

# Configure the logging module
logging.basicConfig(
    level=logging.INFO,  # Log all INFO and higher level messages
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Output logs to console
)

def add_expense(
    amount,
    category,
    description,
    date=None,
    currency='INR',
    payment_method='Credit Card',
    status='paid',
    tags=None,
    location=None,
    receipt=None,
    notes=None
):
    """
    Add an expense record to the system and return its ID.

    This function creates an expense entry with the provided details and inserts it into 
    the database collection. If certain optional fields are not provided, they will 
    default to predefined values. The function also validates that the provided amount 
    is positive.

    Parameters:
    - amount (float or Decimal): The amount of the expense. Must be greater than zero.
    - category (str): The category of the expense (e.g., 'Travel', 'Food').
    - description (str): A brief description of the expense (e.g., 'Flight to New York').
    - date (str, optional): The date of the expense in 'YYYY-MM-DD' format. Defaults to the current date if not provided.
    - currency (str, optional): The currency of the expense. Defaults to 'INR' (Indian Rupee).
    - payment_method (str, optional): The method of payment. Defaults to 'Credit Card'.
    - status (str, optional): The status of the expense. Defaults to 'paid'.
    - tags (list, optional): A list of tags associated with the expense. Defaults to an empty list.
    - location (str, optional): The location where the expense was incurred. Defaults to None.
    - receipt (str, optional): A URL or path to a receipt image/file. Defaults to None.
    - notes (str, optional): Additional notes about the expense. Defaults to None.

    Raises:
    - ValueError: If the amount is less than or equal to zero.

    Returns:
    - str or ObjectId: The MongoDB document ID of the newly inserted expense.
    """
    # Log function call with input parameters
    logging.info(f"Adding expense: {amount} {currency} for {category} - {description}")

    # Validate that the amount is positive
    if amount <= 0:
        logging.error("Invalid amount: Must be greater than zero.")
        raise ValueError("Amount must be greater than zero.")
    
    # If no date is provided, set it to the current date
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # Default to an empty list for tags if none provided
    if tags is None:
        tags = []

    # Prepare the expense data structure
    expense = {
        'amount': Decimal(amount),  # Store amount as Decimal for precision
        'category': category,
        'description': description,
        'date': date,
        'currency': currency,  # Defaults to 'INR'
        'payment_method': payment_method,  # Defaults to 'Credit Card'
        'status': status,  # Defaults to 'paid'
        'tags': tags,  # Defaults to empty list
        'location': location,  # Optional, defaults to None
        'receipt': receipt,  # Optional, defaults to None
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'notes': notes  # Optional, defaults to None
    }

    try:
        # Log database insertion attempt
        logging.info("Inserting expense into the database...")
        
        # Insert the expense into the MongoDB collection and get the inserted document's ID
        result = expenses_collection.insert_one(expense)
        
        # Log successful insertion
        logging.info(f"Expense added successfully with ID: {result.inserted_id}")
        
        # Return the ID of the inserted expense
        return result.inserted_id

    except Exception as e:
        # Log any exception that occurs during the insertion
        logging.error(f"Error inserting expense into database: {e}")
        raise
