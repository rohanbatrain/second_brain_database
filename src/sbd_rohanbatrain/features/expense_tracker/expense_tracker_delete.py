def delete_expense(expense_id):
    """
    Delete an expense record from the system by its unique identifier.

    Parameters:
    - expense_id (str): The unique identifier of the expense to delete.

    Returns:
    - dict: A summary of the delete operation.
    """
    # Convert string ID to ObjectId for MongoDB
    try:
        expense_object_id = ObjectId(expense_id)
    except Exception as e:
        raise ValueError(f"Invalid expense ID: {expense_id}. Error: {e}")

    # Perform the delete operation
    result = expenses_collection.delete_one({'_id': expense_object_id})

    # Return operation summary
    return {
        'deleted_count': result.deleted_count,
        'expense_id': expense_id
    }