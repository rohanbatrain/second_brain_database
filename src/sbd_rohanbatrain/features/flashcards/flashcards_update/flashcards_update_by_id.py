import pymongo
import datetime
from bson import ObjectId
from sbd_rohanbatrain.database.db import flashcards_collection

# Function to retrieve a flashcard from the database by its unique ObjectId
def get_flashcard_by_id(flashcard_id):
    """
    Retrieve a flashcard from the MongoDB collection based on its unique ObjectId.
    
    Parameters:
    flashcard_id (str): The unique identifier (ObjectId) of the flashcard.
    
    Returns:
    dict: The flashcard data as a dictionary, or None if not found.
    """
    flashcard = flashcards_collection.find_one({"_id": ObjectId(flashcard_id)})
    return flashcard


# Function to calculate the next review interval, ease factor, and other review data
def calculate_new_values(grade, current_interval, current_ease_factor, repetitions):
    """
    Calculate the next review interval, ease factor, and other flashcard properties
    based on the user's grade. This function implements the logic of spaced repetition.
    
    Parameters:
    grade (int): The user's grade for the flashcard, representing how well they remembered it.
                - 0: Very hard to recall
                - 1-2: Difficult
                - 3-4: Easy
                - 5: Very easy
    current_interval (int): The current interval (in days) before the next review.
    current_ease_factor (float): The ease factor determines how quickly the interval grows.
    repetitions (int): The number of times the user has reviewed this flashcard.
    
    Returns:
    tuple: A tuple containing the following values:
           - new_interval (int): The new interval for the next review in days.
           - new_ease_factor (float): The updated ease factor after the user's grade.
           - new_repetitions (int): The updated number of repetitions.
           - next_review_date (datetime): The calculated next review date.
    """
    if grade <= 2:
        # If the user grades the card poorly (0-2), reset the interval to 1 day.
        interval = 1  # The next review should happen in 1 day
        ease_factor = current_ease_factor - 0.1  # Ease factor decreases if it's difficult to recall
    else:
        # For better grades, calculate the new interval by multiplying the current interval
        # with the ease factor. This increases the review interval as the user recalls the card.
        interval = round(current_interval * current_ease_factor)
        
        # If the grade is 5 (very easy), increase the ease factor significantly.
        if grade == 5:
            ease_factor = current_ease_factor + 0.2  # Increase ease factor for an easy recall
        else:
            ease_factor = current_ease_factor + 0.1  # Slight increase for easy but not perfect recall

    # Ensure the ease factor doesn't drop below 1.3, which is the minimum allowed by many systems.
    ease_factor = max(ease_factor, 1.3)

    # Increment the number of repetitions (i.e., how many times the card has been reviewed).
    new_repetitions = repetitions + 1

    # Calculate the next review date based on the new interval.
    next_review_date = datetime.datetime.now() + datetime.timedelta(days=interval)  # Use local time

    return interval, ease_factor, new_repetitions, next_review_date


# Function to update the flashcard in the database after a user reviews it
def update_flashcard(flashcard_id, grade):
    """
    Update a flashcard's review data after a user reviews it and provides a grade.
    
    Parameters:
    flashcard_id (str): The unique ID of the flashcard to be updated.
    grade (int): The grade given by the user based on their recall of the flashcard.
                - 0: Very hard to recall
                - 1-2: Difficult
                - 3-4: Easy
                - 5: Very easy
    
    Returns:
    dict: The updated flashcard data after review, including new interval, ease factor, and next review date.
    """
    # Retrieve the flashcard from the database by its ID
    flashcard = get_flashcard_by_id(flashcard_id)

    if not flashcard:
        print(f"Flashcard with ID {flashcard_id} not found.")
        return

    # Get the current values from the flashcard document in the database
    current_interval = flashcard['interval']
    current_ease_factor = flashcard['ease_factor']
    repetitions = flashcard['repetitions']

    # Calculate the new review data based on the user's grade
    interval, ease_factor, new_repetitions, next_review_date = calculate_new_values(
        grade, current_interval, current_ease_factor, repetitions
    )

    # Prepare the updated flashcard data
    updated_flashcard = {
        'interval': interval,
        'ease_factor': ease_factor,
        'repetitions': new_repetitions,
        'next_review_date': next_review_date,
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Time of update in local time
    }

    # Update the flashcard in the MongoDB collection
    flashcards_collection.update_one(
        {"_id": ObjectId(flashcard_id)},  # Match the flashcard by its ObjectId
        {"$set": updated_flashcard}  # Update the flashcard fields with the new values
    )

    print(f"Flashcard updated with new values: {updated_flashcard}")
    return updated_flashcard
