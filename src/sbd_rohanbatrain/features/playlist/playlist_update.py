from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import playlist_collection


# Update the playlist title
def update_playlist_title(playlist_id, new_title):
    """
    Updates the title of a playlist.

    Args:
        playlist_id (str): The ID of the playlist to update.
        new_title (str): The new title for the playlist.

    Returns:
        bool: True if the playlist was updated, False otherwise.
    """
    try:
        playlist_collection = get_playlists_collection()
        result = playlist_collection.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$set": {"title": new_title}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error updating playlist: {e}")
        return False




# Add a song ID to an existing playlist
def add_song_to_playlist(playlist_id, song_id):
    """
    Adds a song ID to an existing playlist.

    Args:
        playlist_id (str): The ID of the playlist.
        song_id (str): The ID of the song to add to the playlist.

    Returns:
        bool: True if the song was added, False otherwise.
    """
    try:
        playlist_collection = get_playlists_collection()
        result = playlist_collection.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$push": {"song_ids": ObjectId(song_id)}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error adding song to playlist: {e}")
        return False
