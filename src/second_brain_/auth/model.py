"""
model.py

User model and data access for authentication in Second Brain Database.

Dependencies:
    - pymongo
    - bson
    - bcrypt
    - Second_Brain_Database.database

Author: Rohan Batra
Date: 2025-06-11
"""

import bcrypt
from bson.objectid import ObjectId
from second_brain_database.database import db

# Initialize MongoDB connection
users_collection = db["users"]  # The users collection


class User:
    """
    User model for authentication and user management.

    Attributes:
        username (str): The user's username.
        email (str): The user's email address.
        password_hash (str): The hashed password.
        plan (str): The user's plan.
        team (list): The user's team members.
        role (str): The user's role (default: "default").
        is_verified (bool): Whether the user's email is verified.
    """

    def __init__(
        self, username, email, password_hash, plan, team=None, role="default", is_verified=False
    ):  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.plan = plan
        self.team = team or []  # Default to empty list if no team is provided
        self.role = role
        self.is_verified = is_verified

    @classmethod
    def find_by_email(cls, email):
        """
        Find a user by their email.

        Args:
            email (str): The user's email address.

        Returns:
            User or None: The User object if found, else None.
        """
        user_data = users_collection.find_one({"email": email})
        if user_data:
            # Remove _id before passing to the constructor
            user_data.pop("_id", None)
            return cls(**user_data)
        return None

    @classmethod
    def find_by_username(cls, username):
        """
        Find a user by their username.

        Args:
            username (str): The user's username.

        Returns:
            User or None: The User object if found, else None.
        """
        user_data = users_collection.find_one({"username": username})
        if user_data:
            # Remove _id before passing to the constructor
            user_data.pop("_id", None)
            return cls(**user_data)
        return None

    def save(self):
        """
        Save a new user to the MongoDB collection.

        Returns:
            User: The saved User object.
        """
        user_data = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "plan": self.plan,
            "team": self.team,
            "role": self.role,
            "is_verified": self.is_verified,
        }
        users_collection.insert_one(user_data)
        return self

    def verify_password(self, password):
        """
        Verify a user's password using bcrypt.

        Args:
            password (str): The plain text password to verify.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @classmethod
    def find_by_id(cls, user_id):
        """
        Find a user by their ID.

        Args:
            user_id (str): The user's ID.

        Returns:
            User or None: The User object if found, else None.
        """
        user_data = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            # Remove _id before passing to the constructor
            user_data.pop("_id", None)
            return cls(**user_data)
        return None

    def update(self, **kwargs):
        """
        Update user details.

        Args:
            **kwargs: Key-value pairs of attributes to update.

        Returns:
            User: The updated User object.
        """
        update_data = {key: value for key, value in kwargs.items() if value is not None}
        users_collection.update_one({"email": self.email}, {"$set": update_data})
        for key, value in update_data.items():
            setattr(self, key, value)
        return self

    def delete(self):
        """
        Delete a user from the MongoDB collection.

        Returns:
            None
        """
        users_collection.delete_one({"email": self.email})
