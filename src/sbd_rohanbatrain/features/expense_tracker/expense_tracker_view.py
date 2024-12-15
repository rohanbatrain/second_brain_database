from sbd_rohanbatrain.database.db import expense_collection

def read_expenses(filters=None):
    """
    Retrieve expense records from the system based on optional filters.

    Parameters:
    - filters (dict, optional): A dictionary of query filters (e.g., {'category': 'Food'}).

    Returns:
    - list: A list of matching expense records.
    """
    # If no filters are provided, default to an empty dictionary (fetch all)
    if filters is None:
        filters = {}

    # Query the MongoDB collection
    results = expenses_collection.find(filters)

    # Convert MongoDB cursor to a list
    return list(results)



