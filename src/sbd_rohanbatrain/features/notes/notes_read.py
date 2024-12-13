def get_current_note(note_id):
    # Retrieve the note from MongoDB
    note = notes_collection.find_one({"_id": note_id})
    
    if note:
        print(f"Title: {note['title']}")
        print(f"Current Version: {note['version']}")
        print(f"Content: {note['content']}")
        print(f"Last Updated: {note['updated_at']}")
    else:
        print("Note not found.")

def get_note_versions(note_id):
    # Retrieve the note from MongoDB
    note = notes_collection.find_one({"_id": note_id})
    
    if note:
        print(f"Title: {note['title']}")
        print(f"Version History:")
        for v in note["version_history"]:
            print(f"Version {v['version']} - {v['updated_at']}: {v['content']}")
    else:
        print("Note not found.")

def get_specific_version(note_id, version_number):
    # Retrieve the note from MongoDB
    note = notes_collection.find_one({"_id": note_id})
    
    if note:
        # Check if the requested version is the current version
        if version_number == note["version"]:
            print(f"Current Version: {note['content']}")
        else:
            # Find the specific version in the history
            for v in note["version_history"]:
                if v["version"] == version_number:
                    print(f"Version {version_number} Content: {v['content']}")
                    break
            else:
                print(f"Version {version_number} not found.")
    else:
        print("Note not found.")
