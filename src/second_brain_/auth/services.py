"""
services.py

Authentication and user management services for Second Brain Database.

Dependencies:
    - bcrypt
    - jwt
    - flask_mail
    - itsdangerous
    - Second_Brain_Database.auth.model
    - Second_Brain_Database.config

Author: Rohan Batra
Date: 2025-06-11
"""

from datetime import datetime, timedelta
import bcrypt
import jwt
from flask_mail import Message, Mail
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, request
from second_brain_database.auth.model import User
from second_brain_database.config import SECRET_KEY, JWT_EXPIRY, MAIL_DEFAULT_SENDER

serializer = URLSafeTimedSerializer(SECRET_KEY)

# Initialize the Mail object
mail = Mail()


def hash_password(password):
    """
    Hash the user's password using bcrypt.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(stored_password_hash, password):
    """
    Verify the password against the stored hash using bcrypt.

    Args:
        stored_password_hash (str): The hashed password from the database.
        password (str): The plain text password to verify.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8'))


def create_user(username, email, password, plan="free", team=None):
    """
    Create a new user and store them in the database.

    Args:
        username (str): The username for the new user.
        email (str): The user's email address.
        password (str): The user's password (plain text).
        plan (str, optional): The user's plan. Defaults to "free".
        team (list, optional): The user's team. Defaults to None.

    Returns:
        User: The created User object.
    """
    if not team:
        team = []  # Default to empty list if no team is provided
    hashed_password = hash_password(password)

    # Create a new user instance
    user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        plan=plan,
        team=team,
    )

    # Save the user in the database (assuming the save method is implemented)
    user.save()
    return user


def create_admin_user(
    username,
    email,
    password,
    plan="free",
    team=None,
    role="admin",
):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """
    Create a new admin user and store them in the database.

    Args:
        username (str): The username for the new admin user.
        email (str): The admin user's email address.
        password (str): The admin user's password (plain text).
        plan (str, optional): The admin user's plan. Defaults to "free".
        team (list, optional): The admin user's team. Defaults to None.
        role (str, optional): The role of the user. Defaults to "admin".

    Returns:
        User: The created admin User object.
    """
    if not team:
        team = []  # Default to empty list if no team is provided
    hashed_password = hash_password(password)

    # Create a new user instance
    user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        plan=plan,
        team=team,
        role=role,
    )

    # Save the user in the database (assuming the save method is implemented)
    user.save_admin()  # pylint: disable=no-member
    return user


def generate_jwt_token(user):
    """
    Generate JWT token for the user.

    Args:
        user (User): The user object for whom the token is generated.

    Returns:
        str: The generated JWT token.
    """
    payload = {
        "sub": user.email,  # Using email as subject
        "username": user.username,  # Include username in payload
        "email": user.email,  # Include email in payload
        "role": user.role,
        "exp": datetime.now()
        + timedelta(hours=int(JWT_EXPIRY.split("h")[0])),  # Expiry
    }

    # Create the JWT token
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def authenticate_user(email, password):
    """
    Authenticate the user with email and password.

    Args:
        email (str): The user's email address.
        password (str): The user's password (plain text).

    Returns:
        User or None: The authenticated User object if successful, None otherwise.
    """
    # Find the user by email
    user = User.find_by_email(email)
    if not user or not verify_password(user.password_hash, password):
        return None  # Authentication failed
    return user


def decode_jwt_token(token):
    """
    Decode the JWT token.

    Args:
        token (str): The JWT token to decode.

    Returns:
        dict or None: The decoded payload if successful, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def send_verification_email(email):
    """
    Send a verification email to the user.

    Args:
        email (str): The user's email address.

    Returns:
        None
    """
    try:
        token = serializer.dumps(email, salt="email-verification")
        verification_url = f"{request.url_root}verify-email?token={token}"
        msg = Message(
            "Verify Your Email",
            sender=MAIL_DEFAULT_SENDER,
            recipients=[email],
            body=f"Please verify your email by clicking the link: {verification_url}",
        )
        mail.send(msg)
    except Exception as e:  # pylint: disable=broad-exception-caught
        current_app.logger.error(f"Failed to send verification email: {e}")
