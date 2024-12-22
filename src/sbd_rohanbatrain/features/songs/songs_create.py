from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import songs_collection

# Create a new song
def create_song(title, artist, duration, url, platform):
    """
    Creates a new song in the songs collection.

    Args:
        title (str): The title of the song.
        artist (str): The artist of the song.
        duration (int): The duration of the song in seconds.
        url (str): The URL for the song (e.g., Spotify or YouTube link).
        platform (str): The platform where the song is hosted.

    Returns:
        str: The ID of the created song, or None if an error occurs.
    """
    try:
        song = {
            "title": title,
            "artist": artist,
            "duration": duration,
            "url": url,
            "platform": platform
        }
         
        result = songs_collection.insert_one(song)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating song: {e}")
        return None

