#!/bin/bash
BASE_URL="http://localhost:5000/user/v1/emotion_tracker"
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
        }' | jq -r '.token')  # Assumes the response has a 'token' field

    if [ -z "$TOKEN" ]; then
        echo "Login failed. Exiting..."
        exit 1
    fi
}

# Function to add a new emotion entry
add_emotion() {
    response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "note_type": "Personal",
            "emotion_felt": "Happy",
            "emotion_intensity": 8,
            "note_ids": ["12345", "67890"]  # Changed to handle multiple note IDs
        }')
    
    if [ "$response" -eq 201 ]; then
        REPORT+="[PASS] Add Emotion: Success\n"
    else
        REPORT+="[FAIL] Add Emotion: Status $response\n"
    fi
}

# Function to get all emotion entries
get_all_emotions() {
    response=$(curl -s -w "%{http_code}" -o /dev/null -X GET "$BASE_URL/get" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$response" -eq 200 ]; then
        REPORT+="[PASS] Get All Emotions: Success\n"
    else
        REPORT+="[FAIL] Get All Emotions: Status $response\n"
    fi
}

# Function to get a single emotion entry by ID
get_emotion_by_id() {
    local emotion_id=$1
    response=$(curl -s -w "%{http_code}" -o /dev/null -X GET "$BASE_URL/get/$emotion_id" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$response" -eq 200 ]; then
        REPORT+="Fetching emotion with ID $emotion_id: Success\n"
    else
        REPORT+="Fetching emotion with ID $emotion_id: Failed with status $response\n"
    fi
}

# Function to update an emotion entry
update_emotion() {
    local emotion_id=$1
    response=$(curl -s -w "%{http_code}" -o /dev/null -X PUT "$BASE_URL/update/$emotion_id" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "note_type": "Personal",
            "emotion_felt": "Sad",
            "emotion_intensity": 5,
            "note": "Had a bad day"
        }')
    
    if [ "$response" -eq 200 ]; then
        REPORT+="Updating emotion with ID $emotion_id: Success\n"
    else
        REPORT+="Updating emotion with ID $emotion_id: Failed with status $response\n"
    fi
}

# Function to delete an emotion entry
delete_emotion() {
    local emotion_id=$1
    response=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "$BASE_URL/delete/$emotion_id" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$response" -eq 200 ]; then
        REPORT+="[PASS] Delete Emotion ID $emotion_id: Success\n"
    else
        REPORT+="[FAIL] Delete Emotion ID $emotion_id: Status $response\n"
    fi
}

# Main script execution
echo "Logging in user..."
login_user

# Add a new emotion entry
echo "Adding a new emotion entry..."
add_emotion

# Get all emotion entries
echo "Fetching all emotion entries..."
get_all_emotions

# Assuming we get an emotion ID from the previous response, for testing, let's use an ID (e.g., "67d0026b98c4a430351fe59d")
EMOTION_ID="67d0026b98c4a430351fe59d"

# Delete the emotion entry
echo "Deleting emotion with ID $EMOTION_ID..."
delete_emotion $EMOTION_ID

# Final Report
echo -e "\n--- Test Report ---"
echo -e "$REPORT"