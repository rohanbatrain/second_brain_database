from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import playlist_collection

# Create a new playlist
def create_playlist(title, created_by, platform, song_ids):
    """
    Creates a new playlist in the playlists collection.

    Args:
        title (str): The title of the playlist.
        created_by (str): The user ID or name of the playlist creator.
        platform (str): The platform where the playlist is hosted.
        song_ids (list): A list of song IDs to include in the playlist.

    Returns:
        str: The ID of the created playlist, or None if an error occurs.
    """
    try:
        playlist = {
            "title": title,
            "created_by": created_by,
            "platform": platform,
            "song_ids": [ObjectId(song_id) for song_id in song_ids],
            "created_at": datetime.now()
        }
        result = playlist_collection.insert_one(playlist)
        return str(result.inserted_id)  # Return the inserted playlist ID
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
