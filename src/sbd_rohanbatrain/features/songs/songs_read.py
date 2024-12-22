from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import songs_collection

# Fetch a song by ID
def get_song(song_id):
    """
    Retrieves a song by its ID.

    Args:
        song_id (str): The ID of the song to retrieve.

    Returns:
        dict: The song document, or None if the song is not found or an error occurs.
    """
    try:
        songs_collection = get_songs_collection()
        song = songs_collection.find_one({"_id": ObjectId(song_id)})
        return song if song else None
    except Exception as e:
        print(f"Error fetching song: {e}")
        return None