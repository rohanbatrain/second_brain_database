from sbd_rohanbatrain.database.db import labels_collection
from bson import ObjectId
 

def delete_label(label_id):
    """
    Deletes a label from the database by its ID.

    Parameters:
    label_id (str): The unique identifier of the label to be deleted.

    Returns:
    int: The number of labels deleted.
    """
    result = labels_collection.delete_one({"_id": ObjectId(label_id)})
    return result.deleted_count
