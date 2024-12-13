import datetime
import uuid
import markdown
import re
from sbd_rohanbatrain.database.db import notes_collection
from bson import ObjectId  # MongoDB ObjectId

# Function to convert raw Markdown to HTML
def convert_markdown_to_html(content):
    """Convert Markdown content to HTML."""
    return markdown.markdown(content)

# Function to detect links in the content
def detect_links_in_content(content):
    """Detect links in the Markdown content."""
    return [link.strip("[[]]") for link in content.split() if link.startswith("[[") and link.endswith("]]")]

# Function to update linked notes with this note as a back-link
def update_linked_notes(note_id, links):
    """Update linked notes with back-links."""
    for link in links:
        linked_note = notes_collection.find_one({"title": link})
        if linked_note:
            linked_note["linked_notes"].append(note_id)
            notes_collection.update_one(
                {"_id": linked_note["_id"]},
                {"$set": {"linked_notes": linked_note["linked_notes"]}}
            )

# Function to create a new note in the database
def create_note_in_db(notename, content, html_content, links):
    """Create a new note in MongoDB."""
    # Generate a new MongoDB ObjectId for the note
    note_id = str(ObjectId())

    # Get the current timestamp
    created_at = updated_at = datetime.datetime.now().isoformat()

    # Default tags to an empty list
    tags = []

    # Create the note in MongoDB with auto-generated _id, tags, links, and markdown support
    note = {
        "_id": note_id,
        "title": notename,
        "content": content,  # Raw Markdown content
        "html_content": html_content,  # HTML content converted from Markdown
        "tags": tags,
        "links": links,
        "created_at": created_at,
        "updated_at": updated_at,
        "version": 1,
        "version_history": []
    }

    # Insert the note into the database
    notes_collection.insert_one(note)

    return note_id, links

# Main function to add a note
def add_note_with_links(notename, content):
    """Create a note with links and Markdown support."""
    # Convert Markdown content to HTML
    html_content = convert_markdown_to_html(content)

    # Detect links in the content
    links = detect_links_in_content(content)

    # Create the note in the database
    note_id, links = create_note_in_db(notename, content, html_content, links)

    # Update linked notes with this note as a back-link
    update_linked_notes(note_id, links)

    print(f"Note '{notename}' created with version 1, ID {note_id}, links {links}.")
