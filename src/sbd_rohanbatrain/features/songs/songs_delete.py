from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import songs_collection

# Delete a song by ID
def delete_song(song_id):
    """
    Deletes a song by its ID.

    Args:
        song_id (str): The ID of the song to delete.

    Returns:
        bool: True if the song was deleted, False otherwise.
    """
    try:
        songs_collection = get_songs_collection()
        result = songs_collection.delete_one({"_id": ObjectId(song_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting song: {e}")
        return False
