from pymongo import MongoClient
from passlib.hash import bcrypt
from bson.objectid import ObjectId
from Second_Brain_Database.database import db

# Initialize MongoDB connection
users_collection = db["users"]  # The users collection

class User:
    def __init__(self, username, email, password_hash, plan, team=None):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.plan = plan
        self.team = team or []  # Default to empty list if no team is provided


    @classmethod
    def find_by_email(cls, email):
        """Find a user by their email."""
        user_data = users_collection.find_one({"email": email})
        if user_data:
            # Remove _id before passing to the constructor
            user_data.pop('_id', None)
            return cls(**user_data)
        return None

    @classmethod
    def find_by_username(cls, username):
        """Find a user by their username."""
        user_data = users_collection.find_one({"username": username})
        if user_data:
            # Remove _id before passing to the constructor
            user_data.pop('_id', None)
            return cls(**user_data)
        return None

    def save(self):
        """Save a new user to the MongoDB collection."""
        user_data = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "plan": self.plan,
            "team": self.team,
            # "is_admin": self.is_admin
        }
        result = users_collection.insert_one(user_data)
        return self

    def save_admin(self):
        """Save a new admin to the MongoDB collection."""
        user_data = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "plan": self.plan,
            "team": self.team,
            "is_admin": True
        }
        result = users_collection.insert_one(user_data)
        return self

    def verify_password(self, password):
        """Verify a user's password."""
        return bcrypt.verify(password, self.password_hash)
