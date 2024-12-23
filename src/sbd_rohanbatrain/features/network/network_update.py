from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from sbd_rohanbatrain.database.db import network_collection

collection = network_collection

def update_entry(
    entry_id: str, 
    first_name: Optional[str] = None, 
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
    snapchat_handle: Optional[str] = None,  
    telegram_handle: Optional[str] = None,  
    youtube_handle: Optional[str] = None,  
    medium_handle: Optional[str] = None,   
    github_handle: Optional[str] = None,   
    pinterest_handle: Optional[str] = None, 
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
    labels: Optional[List[str]] = None
) -> bool:
    """
    Update an existing entry in MongoDB by its ID. This function allows updating any combination of fields, including personal information, contact details, social media profiles, addresses, and professional information. The `last_updated` field will always be updated to the current timestamp.

    Args:
        entry_id (str): The ID of the entry to update.
        first_name (Optional[str]): Updated first name (default: None).
        middle_name (Optional[str]): Updated middle name (default: None).
        last_name (Optional[str]): Updated last name (default: None).
        date_of_birth (Optional[str]): Updated date of birth in 'YYYY-MM-DD' format (default: None).
        gender (Optional[str]): Updated gender (default: None).
        email1 (Optional[str]): Updated primary email address (default: None).
        email2 (Optional[str]): Updated secondary email address (default: None).
        phone1 (Optional[str]): Updated primary phone number (default: None).
        phone2 (Optional[str]): Updated secondary phone number (default: None).
        instagram_handle (Optional[str]): Updated Instagram handle (default: None).
        twitter_handle (Optional[str]): Updated Twitter handle (default: None).
        facebook_handle (Optional[str]): Updated Facebook handle (default: None).
        linkedin_handle (Optional[str]): Updated LinkedIn handle (default: None).
        snapchat_handle (Optional[str]): Updated Snapchat handle (default: None).
        telegram_handle (Optional[str]): Updated Telegram handle (default: None).
        youtube_handle (Optional[str]): Updated YouTube handle (default: None).
        medium_handle (Optional[str]): Updated Medium handle (default: None).
        github_handle (Optional[str]): Updated GitHub handle (default: None).
        pinterest_handle (Optional[str]): Updated Pinterest handle (default: None).
        home_street (Optional[str]): Updated home street address (default: None).
        home_city (Optional[str]): Updated home city (default: None).
        home_state (Optional[str]): Updated home state (default: None).
        home_postal_code (Optional[str]): Updated home postal code (default: None).
        home_country (Optional[str]): Updated home country (default: None).
        work_street (Optional[str]): Updated work street address (default: None).
        work_city (Optional[str]): Updated work city (default: None).
        work_state (Optional[str]): Updated work state (default: None).
        work_postal_code (Optional[str]): Updated work postal code (default: None).
        work_country (Optional[str]): Updated work country (default: None).
        occupation (Optional[str]): Updated occupation/job title (default: None).
        company (Optional[str]): Updated company name (default: None).
        relationship (Optional[str]): Updated relationship (e.g., friend, colleague, etc.) (default: None).
        interests (Optional[List[str]]): Updated list of hobbies or interests (default: None).
        labels (Optional[List[str]]): Updated list of labels or tags for categorization (default: None).

    Returns:
        bool: `True` if the update was successful, `False` otherwise.

    Raises:
        ValueError: If no fields are provided to update or if the `date_of_birth` format is invalid.
        RuntimeError: If any error occurs during the update process (e.g., MongoDB update failure).

    Example:
        result = update_entry(
            entry_id="60f98fbc8f1b2c3a1b2c3d4f",
            first_name="John",
            last_name="Doe",
            instagram_handle="john_doe_updated",
            phone1="9876543210",
            occupation="Senior Developer",
            relationship="Colleague"
        )
        print(result)  # Output: True (if update is successful)
    """
    # Prepare the update fields dictionary
    update_fields = {}

    # Personal Information
    if first_name:
        update_fields["first_name"] = first_name
    if middle_name:
        update_fields["middle_name"] = middle_name
    if last_name:
        update_fields["last_name"] = last_name
    if date_of_birth:
        try:
            update_fields["date_of_birth"] = datetime.strptime(date_of_birth, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date_of_birth format. Use 'YYYY-MM-DD'.")
    if gender:
        update_fields["gender"] = gender

    # Contact Information
    if email1 or email2:
        update_fields["contact_info"] = update_fields.get("contact_info", {})
        update_fields["contact_info"]["emails"] = [email1, email2] if email1 or email2 else None
    if phone1 or phone2:
        update_fields["contact_info"] = update_fields.get("contact_info", {})
        update_fields["contact_info"]["phone_numbers"] = [phone1, phone2] if phone1 or phone2 else None

    # Social Media Information
    social_media = {}
    if instagram_handle:
        social_media["instagram"] = instagram_handle
    if twitter_handle:
        social_media["twitter"] = twitter_handle
    if facebook_handle:
        social_media["facebook"] = facebook_handle
    if linkedin_handle:
        social_media["linkedin"] = linkedin_handle
    if snapchat_handle:
        social_media["snapchat"] = snapchat_handle
    if telegram_handle:
        social_media["telegram"] = telegram_handle
    if youtube_handle:
        social_media["youtube"] = youtube_handle
    if medium_handle:
        social_media["medium"] = medium_handle
    if github_handle:
        social_media["github"] = github_handle
    if pinterest_handle:
        social_media["pinterest"] = pinterest_handle
    if social_media:
        update_fields["contact_info"] = update_fields.get("contact_info", {})
        update_fields["contact_info"]["social_media"] = social_media

    # Address Information
    address_info = {}
    if home_street or home_city or home_state or home_postal_code or home_country:
        address_info["home_address"] = {
            "street": home_street,
            "city": home_city,
            "state": home_state,
            "postal_code": home_postal_code,
            "country": home_country,
        }
    if work_street or work_city or work_state or work_postal_code or work_country:
        address_info["work_address"] = {
            "street": work_street,
            "city": work_city,
            "state": work_state,
            "postal_code": work_postal_code,
            "country": work_country,
        }
    if address_info:
        update_fields["address"] = address_info

    # Professional Information
    if occupation:
        update_fields["occupation"] = occupation
    if company:
        update_fields["company"] = company

    # Relationship
    if relationship:
        update_fields["relationship"] = relationship

    # Interests and Labels
    if interests is not None:
        update_fields["interests"] = interests
    if labels is not None:
        update_fields["labels"] = labels

    # Always update the `last_updated` field
    update_fields["last_updated"] = datetime.now()

    if not update_fields:
        raise ValueError("No fields to update.")

    try:
        # Perform the update
        result = collection.update_one(
            {"_id": ObjectId(entry_id)}, 
            {"$set": update_fields}
        )

        return result.matched_count > 0

    except Exception as e:
        raise RuntimeError(f"An error occurred while updating the entry: {str(e)}")


def append_phone_number(entry_id: str, phone_number: str) -> bool:
    """
    Append a new phone number to the contact information of an existing entry.

    Args:
        entry_id (str): The ID of the entry to update.
        phone_number (str): The phone number to append.

    Returns:
        bool: `True` if the update was successful, `False` otherwise.

    Raises:
        ValueError: If the phone number is invalid or if no phone number is provided.
    """
    if not phone_number:
        raise ValueError("Phone number cannot be empty.")

    try:
        # Perform the update to append the new phone number
        result = collection.update_one(
            {"_id": ObjectId(entry_id)},
            {
                "$push": {
                    "contact_info.phone_numbers": phone_number
                },
                "$set": {
                    "last_updated": datetime.now()
                }
            }
        )
        
        return result.matched_count > 0

    except Exception as e:
        raise RuntimeError(f"An error occurred while appending the phone number: {str(e)}")


def append_email(entry_id: str, email: str) -> bool:
    """
    Append a new email address to the contact information of an existing entry.

    Args:
        entry_id (str): The ID of the entry to update.
        email (str): The email address to append.

    Returns:
        bool: `True` if the update was successful, `False` otherwise.

    Raises:
        ValueError: If the email address is invalid or if no email is provided.
    """
    if not email:
        raise ValueError("Email cannot be empty.")

    try:
        # Perform the update to append the new email address
        result = collection.update_one(
            {"_id": ObjectId(entry_id)},
            {
                "$push": {
                    "contact_info.emails": email
                },
                "$set": {
                    "last_updated": datetime.now()
                }
            }
        )
        
        return result.matched_count > 0

    except Exception as e:
        raise RuntimeError(f"An error occurred while appending the email address: {str(e)}")

# Append a new phone number to an entry
result_phone = append_phone_number("676933f1d27745b1db9450b2", "66676543210")
print(result_phone)  # Output: True (if the phone number is successfully appended)

# Append a new email to an entry
result_email = append_email("676933f1d27745b1db9450b2", "djohn.doe@example.com")
print(result_email)  # Output: True (if the email is successfully appended)
