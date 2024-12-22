from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import playlist_collection

# Delete a playlist
def delete_playlist(playlist_id):
    """
    Deletes a playlist by its ID.

    Args:
        playlist_id (str): The ID of the playlist to delete.

    Returns:
        bool: True if the playlist was deleted, False otherwise.
    """
    try:
        playlist_collection = get_playlists_collection()
        result = playlist_collection.delete_one({"_id": ObjectId(playlist_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting playlist: {e}")
        return False
