from sbd_rohanbatrain.database.db import labels_collection

def delete_label_by_name(label_name):
    """
    Deletes a label from the database by its name.

    Parameters:
    label_name (str): The name of the label to be deleted.

    Returns:
    int: The number of labels deleted (0 or 1).
    """
    result = labels_collection.delete_one({"name": label_name})
    return result.deleted_count
