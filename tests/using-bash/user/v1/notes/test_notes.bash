#!/bin/bash
BASE_URL="http://localhost:5000/user/v1/notes"
AUTH_URL="http://localhost:5000/auth"
TOKEN=""
REPORT=""
NOTE_ID=""

# Function to log in and get the token
login_user() {
    TOKEN=$(curl -s -X POST "$AUTH_URL/login" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "testuser@example.com",
            "password": "password123"
        }' | jq -r '.token')
}

# Function to add a new note (modified to capture NOTE_ID)
add_note() {
    # Capture both the body and the status code
    output=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "title": "Test Note",
            "content": "This is a test note."
        }')
    # Separate the body and the status code
    response_body=$(echo "$output" | sed '$d')
    status_code=$(echo "$output" | tail -n1)
    
    if [ "$status_code" -eq 201 ]; then
        NOTE_ID=$(echo "$response_body" | jq -r '.id')
        REPORT+="Adding new note: Success\n"
    else
        REPORT+="Adding new note: Failed with status $status_code\n"
    fi
}

# Function to get all notes
get_all_notes() {
    response=$(curl -s -X GET "$BASE_URL/get" \
        -H "Authorization: Bearer $TOKEN")
    if [ -z "$response" ]; then
        REPORT+="Fetching all notes: Failed (Empty response)\n"
        echo "Response: (Empty)"
        return
    fi

    # Check if the response is a valid JSON array
    if echo "$response" | jq -e '.[0]' > /dev/null 2>&1; then
        REPORT+="Fetching all notes: Success\n"
        echo "Response: $response"
    else
        REPORT+="Fetching all notes: Failed (Invalid response format)\n"
        echo "Response: $response"
    fi
}

# Function to get a single note by ID
get_note_by_id() {
    local note_id=$1
    response=$(curl -s -X GET "$BASE_URL/get/$note_id" \
        -H "Authorization: Bearer $TOKEN")
    if [ -z "$response" ]; then
        REPORT+="Fetching note with ID $note_id: Failed (Empty response)\n"
        echo "Response: (Empty)"
        return
    fi

    status_code=$(echo "$response" | jq -r '.status_code // empty')
    if [ "$status_code" == "200" ]; then
        REPORT+="Fetching note with ID $note_id: Success\n"
        echo "Response: $response"
    else
        REPORT+="Fetching note with ID $note_id: Failed with status $status_code\n"
        echo "Response: $response"
    fi
}

# Function to update a note
update_note() {
    local note_id=$1
    response=$(curl -s -X PUT "$BASE_URL/update/$note_id" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "title": "Updated Test Note",
            "content": "This is an updated test note."
        }')
    if [ -z "$response" ]; then
        REPORT+="Updating note with ID $note_id: Failed (Empty response)\n"
        echo "Response: (Empty)"
        return
    fi

    status_code=$(echo "$response" | jq -r '.status_code // empty')
    if [ "$status_code" == "200" ]; then
        REPORT+="Updating note with ID $note_id: Success\n"
        echo "Response: $response"
    else
        REPORT+="Updating note with ID $note_id: Failed with status $status_code\n"
        echo "Response: $response"
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

# Replace the sequential commands with an interactive operation menu
while true; do
    echo ""
    echo "Select an operation:"
    echo "1) Login"
    echo "2) Add note"
    echo "3) Get all notes"
    echo "4) Get note by ID"
    echo "5) Update note"
    echo "6) Delete note"
    echo "7) Show Report"
    echo "8) Run all operations sequentially"
    echo "0) Exit"
    read -p "Enter option: " option
    case "$option" in
        1)
            login_user
            echo "Logged in."
            ;;
        2)
            add_note
            echo "Added note. NOTE_ID: $NOTE_ID"
            ;;
        3)
            get_all_notes
            echo "Fetched all notes."
            ;;
        4)
            read -p "Enter Note ID: " input_note_id
            get_note_by_id "$input_note_id"
            echo "Fetched note with ID $input_note_id."
            ;;
        5)
            read -p "Enter Note ID: " input_note_id
            update_note "$input_note_id"
            echo "Updated note with ID $input_note_id."
            ;;
        6)
            read -p "Enter Note ID: " input_note_id
            delete_note "$input_note_id"
            echo "Deleted note with ID $input_note_id."
            ;;
        7)
            echo -e "\n--- Test Report ---"
            echo -e "$REPORT"
            ;;
        8)
            login_user
            add_note
            get_all_notes
            get_note_by_id "$NOTE_ID"
            update_note "$NOTE_ID"
            delete_note "$NOTE_ID"
            echo -e "\n--- Test Report ---"
            echo -e "$REPORT"
            ;;
        0)
            exit 0
            ;;
        *)
            echo "Invalid option. Try again."
            ;;
    esac
    read -p "Press Enter to continue..."
done
