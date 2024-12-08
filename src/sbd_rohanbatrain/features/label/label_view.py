from datetime import datetime
from sbd_rohanbatrain.database.db import labels_collection
from bson import ObjectId


def view_labels():
    """
    Retrieves and displays all labels from the database.

    Returns:
    list: A list of labels from the database.
    """
    labels = labels_collection.find()
    return [{"name": label["name"], "color": label["color"]} for label in labels]