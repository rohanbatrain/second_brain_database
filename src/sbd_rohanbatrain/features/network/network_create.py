from typing import Dict, List, Optional
from datetime import datetime, date
from pymongo.errors import DuplicateKeyError
from sbd_rohanbatrain.database.db import network_collection

collection = network_collection

def create_entry(
    first_name: str, 
    middle_name: Optional[str] = None, 
    last_name: Optional[str] = None, 
    date_of_birth: Optional[str] = None, 
    gender: Optional[str] = None, 
    email1: Optional[str] = None, 
    email2: Optional[str] = None, 
    phone1: Optional[str] = None, 
    phone2: Optional[str] = None, 
    instagram_handle: Optional[str] = None, 
    twitter_handle: Optional[str] = None, 
    facebook_handle: Optional[str] = None, 
    linkedin_handle: Optional[str] = None,
    snapchat_handle: Optional[str] = None,  # Added Snapchat
    telegram_handle: Optional[str] = None,  # Added Telegram
    youtube_handle: Optional[str] = None,  # Added YouTube
    medium_handle: Optional[str] = None,   # Added Medium
    github_handle: Optional[str] = None,   # Added GitHub
    pinterest_handle: Optional[str] = None, # Added Pinterest
    home_street: Optional[str] = None, 
    home_city: Optional[str] = None, 
    home_state: Optional[str] = None, 
    home_postal_code: Optional[str] = None, 
    home_country: Optional[str] = None, 
    work_street: Optional[str] = None, 
    work_city: Optional[str] = None, 
    work_state: Optional[str] = None, 
    work_postal_code: Optional[str] = None, 
    work_country: Optional[str] = None, 
    occupation: Optional[str] = None, 
    company: Optional[str] = None, 
    relationship: Optional[str] = None, 
    interests: Optional[List[str]] = None, 
    labels: Optional[List[str]] = None, 
    date: Optional[str] = None
) -> Dict:
    """
    Create a new entry for a person and insert it into the MongoDB collection. This function allows you to store detailed information about a person in a network, including personal information, contact details, social media handles, addresses, professional details, and more. If a `date` is not provided, the current date and time will be used as the creation and last updated time.

    Args:
        first_name (str): The first name of the person.
        middle_name (Optional[str]): The middle name of the person (default is None).
        last_name (Optional[str]): The last name of the person (default is None).
        date_of_birth (Optional[str]): The date of birth in "YYYY-MM-DD" format (default is None).
        gender (Optional[str]): The gender of the person (default is None).
        email1 (Optional[str]): The primary email address of the person (default is None).
        email2 (Optional[str]): The secondary email address of the person (default is None).
        phone1 (Optional[str]): The primary phone number of the person (default is None).
        phone2 (Optional[str]): The secondary phone number of the person (default is None).
        instagram_handle (Optional[str]): The Instagram username or handle of the person (default is None).
        twitter_handle (Optional[str]): The Twitter username or handle of the person (default is None).
        facebook_handle (Optional[str]): The Facebook username or handle of the person (default is None).
        linkedin_handle (Optional[str]): The LinkedIn username or handle of the person (default is None).
        snapchat_handle (Optional[str]): The Snapchat username or handle of the person (default is None).
        telegram_handle (Optional[str]): The Telegram username or handle of the person (default is None).
        youtube_handle (Optional[str]): The YouTube username or handle of the person (default is None).
        medium_handle (Optional[str]): The Medium username or handle of the person (default is None).
        github_handle (Optional[str]): The GitHub username or handle of the person (default is None).
        pinterest_handle (Optional[str]): The Pinterest username or handle of the person (default is None).
        home_street (Optional[str]): The street address for the home address (default is None).
        home_city (Optional[str]): The city for the home address (default is None).
        home_state (Optional[str]): The state for the home address (default is None).
        home_postal_code (Optional[str]): The postal code for the home address (default is None).
        home_country (Optional[str]): The country for the home address (default is None).
        work_street (Optional[str]): The street address for the work address (default is None).
        work_city (Optional[str]): The city for the work address (default is None).
        work_state (Optional[str]): The state for the work address (default is None).
        work_postal_code (Optional[str]): The postal code for the work address (default is None).
        work_country (Optional[str]): The country for the work address (default is None).
        occupation (Optional[str]): The job title or occupation of the person (default is None).
        company (Optional[str]): The company or organization where the person works (default is None).
        relationship (Optional[str]): The relationship to the person (e.g., friend, colleague, acquaintance) (default is None).
        interests (Optional[List[str]]): A list of the person's hobbies, favorite activities, or areas of interest (default is an empty list).
        labels (Optional[List[str]]): A list of labels or tags to categorize the person (default is an empty list).
        date (Optional[str]): The creation and last updated timestamp in "YYYY-MM-DD HH:MM:SS" format (default is the current date and time).

    Returns:
        Dict: A dictionary representing the newly created entry with all the provided information, which is also inserted into the MongoDB collection.

    Raises:
        RuntimeError: If any error occurs during the entry creation process, such as issues with inserting into MongoDB.

    Notes:
        - All social media handles are optional and will only be included if the corresponding parameters are provided.
        - The addresses for both home and work are stored separately with fields for street, city, state, postal code, and country.
        - The `labels` and `interests` fields are optional arrays that allow for additional categorization and personalization of the entry.
        - The function uses the current date and time as the `creation_date` and `last_updated` timestamp if no `date` is provided.
        - The function inserts the entry into the MongoDB collection defined by `network_collection` and returns the inserted entry.

    Example:
        entry = create_entry(
            first_name="John", 
            last_name="Doe", 
            email1="johndoe@example.com", 
            phone1="1234567890", 
            instagram_handle="john_doe_123", 
            occupation="Software Engineer", 
            company="Tech Corp", 
            interests=["coding", "gaming"], 
            labels=["friend", "colleague"]
        )
        print(entry)
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Use current date-time if none provided

    try:
        entry = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "gender": gender,
            "date_of_birth": datetime.strptime(date_of_birth, "%Y-%m-%d") if date_of_birth else None,
            
            # Contact Information
            "contact_info": {
                "emails": [email1, email2],  # List of emails
                "phone_numbers": [phone1, phone2],  # List of phone numbers
                "social_media": {
                    "instagram": instagram_handle,
                    "twitter": twitter_handle,
                    "facebook": facebook_handle,
                    "linkedin": linkedin_handle,  # LinkedIn added here
                    "snapchat": snapchat_handle,  # Snapchat added here
                    "telegram": telegram_handle,  # Telegram added here
                    "youtube": youtube_handle,    # YouTube added here
                    "medium": medium_handle,      # Medium added here
                    "github": github_handle,      # GitHub added here
                    "pinterest": pinterest_handle # Pinterest added here
                }
            },
            
            # Address Information
            "address": {
                "home_address": {
                    "street": home_street,
                    "city": home_city,
                    "state": home_state,
                    "postal_code": home_postal_code,
                    "country": home_country,
                },
                "work_address": {
                    "street": work_street,
                    "city": work_city,
                    "state": work_state,
                    "postal_code": work_postal_code,
                    "country": work_country,
                }
            },
            
            # Professional Details
            "occupation": occupation,  # Job title or profession
            "company": company,        # Company name, if applicable
            
            # Relationship and Network
            "relationship": relationship,  # How you know the person (e.g., friend, colleague)
            
            # Interests (Hobbies or activities)
            "interests": interests or [],  # List of hobbies or interests
            
            # Labels/Tags for Categorization
            "labels": labels or [],  # Array of label IDs or tags for categorizing the person
            
            # Timestamps
            "creation_date": date,  # Creation time
            "last_updated": date,   # Last updated time (to be modified on updates)
        }

        # Insert entry into MongoDB
        collection.insert_one(entry)
        return entry

    except Exception as e:
        raise RuntimeError(f"An error occurred while creating the entry: {str(e)}")


