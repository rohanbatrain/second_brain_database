from datetime import datetime
from sbd_rohanbatrain.database.db import projects_collection
from bson import ObjectId

# Fetch a playlist by ID
def get_playlist(playlist_id):
    """
    Retrieves a playlist by its ID.

    Args:
        playlist_id (str): The ID of the playlist to retrieve.

    Returns:
        dict: The playlist document, or None if not found or an error occurs.
    """
    try:
        playlist_collection = get_playlists_collection()
        playlist = playlist_collection.find_one({"_id": ObjectId(playlist_id)})
        return playlist if playlist else None
    except Exception as e:
        print(f"Error retrieving playlist: {e}")
        return None
