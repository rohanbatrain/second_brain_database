#!/bin/bash
BASE_URL="http://localhost:5000/user/v1/notes"
AUTH_URL="http://localhost:5000/auth"
TOKEN=""
REPORT=""

# Function to log in and get the token
login_user() {
    TOKEN=$(curl -s -X POST "$AUTH_URL/login" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "testuser@example.com",
            "password": "password123"
        }' | jq -r '.token')
}

# Function to add a new note
add_note() {
    response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "title": "Test Note",
            "content": "This is a test note."
        }')
    
    if [ "$response" -eq 201 ]; then
        REPORT+="Adding new note: Success\n"
    else
        REPORT+="Adding new note: Failed with status $response\n"
    fi
}

# Function to get all notes
get_all_notes() {
    response=$(curl -s -w "%{http_code}" -o /dev/null -X GET "$BASE_URL/get" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$response" -eq 200 ]; then
        REPORT+="Fetching all notes: Success\n"
    else
        REPORT+="Fetching all notes: Failed with status $response\n"
    fi
}

# Function to delete a note by ID
delete_note() {
    local note_id=$1
    response=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "$BASE_URL/delete/$note_id" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$response" -eq 200 ]; then
        REPORT+="Deleting note with ID $note_id: Success\n"
    else
        REPORT+="Deleting note with ID $note_id: Failed with status $response\n"
    fi
}

# Main script execution
echo "Logging in user..."
login_user

# Add a new note
echo "Adding a new note..."
add_note

# Get all notes
echo "Fetching all notes..."
get_all_notes

# Assuming we get a note ID from the previous response, for testing, let's use an ID (e.g., "12345")
NOTE_ID="12345"

# Delete the note
echo "Deleting note with ID $NOTE_ID..."
delete_note $NOTE_ID

# Final Report
echo -e "\n--- Test Report ---"
echo -e "$REPORT"
