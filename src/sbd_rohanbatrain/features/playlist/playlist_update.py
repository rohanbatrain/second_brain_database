from bson.objectid import ObjectId
from datetime import datetime
from sbd_rohanbatrain.database.db import playlist_collection

# Update any field in the playlist
def update_playlist(playlist_id, title=None, platform=None, item_ids=None):
    """
    Updates various fields of an existing playlist. Fields that are passed as `None` will not be updated.

    Args:
        playlist_id (str): The ID of the playlist to update. This should be the ObjectId (as a string) 
                            of the playlist document you want to modify.
        title (str, optional): The new title for the playlist. If not provided or set to `None`, the title will not be updated.
        platform (str, optional): The new platform for the playlist. If not provided or set to `None`, the platform will not be updated.
        item_ids (list, optional): A list of item IDs (songs, videos, etc.) to update the playlist with. 
                                    If not provided or set to `None`, the item IDs will not be updated.

    Returns:
        bool: Returns `True` if the playlist was successfully updated, and `False` if no documents were updated 
              (e.g., the playlist ID was not found, or no valid fields were provided for the update).

    Raises:
        Exception: If there is an error during the database operation, an exception will be raised and 
                   the error message will be printed.

    Example:
        updated = update_playlist(
            playlist_id="607f1f77bcf86cd799439011", 
            title="New Playlist Title", 
            platform="Spotify"
        )
        if updated:
            print("Playlist updated successfully!")
        else:
            print("Failed to update playlist.")
    """
    update_fields = {}

    if title is not None:
        update_fields["title"] = title
    if platform is not None:
        update_fields["platform"] = platform
    if item_ids is not None:
        update_fields["item_ids"] = [ObjectId(item_id) for item_id in item_ids]

    if not update_fields:
        print("No valid fields to update.")
        return False

    try:
        result = playlist_collection.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$set": update_fields}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error updating playlist: {e}")
        return False

# Add an item (song or video) ID to an existing playlist
def add_item_to_playlist(playlist_id, item_id):
    """
    Adds an item ID (song or video) to an existing playlist.

    Args:
        playlist_id (str): The ID of the playlist to update. This should be the ObjectId (as a string) 
                            of the playlist that you want to add an item to.
        item_id (str): The ID of the item (song or video) to add to the playlist. This should be the ObjectId 
                       (as a string) of the item that you want to add to the `item_ids` field of the playlist.

    Returns:
        bool: Returns `True` if the item was successfully added to the playlist, and `False` if no document 
              was updated (e.g., the playlist ID was not found, or the item ID already exists in the playlist).

    Raises:
        Exception: If there is an error during the database operation, an exception will be raised and 
                   the error message will be printed.

    Example:
        item_added = add_item_to_playlist("607f1f77bcf86cd799439011", "607f1f77bcf86cd799439012")
        if item_added:
            print("Item added to playlist successfully!")
        else:
            print("Failed to add item to playlist.")
    """
    try:
        result = playlist_collection.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$push": {"item_ids": ObjectId(item_id)}}  # Renamed to item_ids
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error adding item to playlist: {e}")
        return False
