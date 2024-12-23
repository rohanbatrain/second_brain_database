from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import playlist_collection

# Create a new playlist
def create_playlist(title, platform, item_ids, playlist_type):
    """
    Creates a new playlist in the playlists collection.

    Args:
        title (str): The title of the playlist. This should be a descriptive name for the playlist, 
                     such as "Chill Vibes" or "Top 50 Songs".
        platform (str): The platform where the playlist is hosted. This can be a platform name like 
                        "Spotify", "YouTube", "Apple Music", etc.
        item_ids (list): A list of item IDs (songs, videos, etc.) to include in the playlist. 
                         Each item ID should be a valid ObjectId that references either a song or video.
        playlist_type (str): The type of the playlist, which indicates whether the playlist contains 
                             songs, videos, or other types of media. Example values could be "songs", 
                             "videos", or "mixed" for a combination of both.

    Returns:
        str: The ID of the created playlist. If successful, the function returns the string representation 
             of the ObjectId of the new playlist. If an error occurs during the playlist creation, 
             the function returns `None`.

    Raises:
        Exception: If there is an error in the database operation, an exception will be printed, and the 
                   function will return `None`.

    Example:
        playlist_id = create_playlist(
            title="Chill Vibes",
            platform="Spotify",
            item_ids=["607f1f77bcf86cd799439011", "607f1f77bcf86cd799439012"],  # Example ObjectIds
            playlist_type="songs"
        )
    """
    try:
        playlist = {
            "title": title,
            "platform": platform,
            "item_ids": [ObjectId(item_id) for item_id in item_ids],  # Ensure item_ids are ObjectIds
            "playlist_type": playlist_type,  # Playlist type indicates the media content (e.g., "songs", "videos")
            "created_at": datetime.now()
        }
        result = playlist_collection.insert_one(playlist)
        return str(result.inserted_id)  # Return the inserted playlist ID
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
