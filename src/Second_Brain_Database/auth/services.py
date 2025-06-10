import bcrypt  # Ensure bcrypt is imported
from datetime import datetime, timedelta
import jwt
from Second_Brain_Database.auth.model import User  # Your User model
from Second_Brain_Database.config import (
    SECRET_KEY,
    JWT_EXPIRY,
)  # Configuration file for secret keys
from flask_mail import Message, Mail
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, request
from Second_Brain_Database.config import MAIL_DEFAULT_SENDER, SECRET_KEY



serializer = URLSafeTimedSerializer(SECRET_KEY)

# Initialize the Mail object
mail = Mail()


def hash_password(password):
    """Hash the user's password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(stored_password_hash, password):
    """Verify the password against the stored hash using bcrypt."""
    return bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8'))


def create_user(username, email, password, plan="free", team=None):
    """Create a new user and store them in the database."""
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


def create_admin_user(username,
                      email,
                      password,
                      plan="free",
                      team=None,
                      role="admin"):
    """Create a new user and store them in the database."""
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
    user.save_admin()
    return user


def generate_jwt_token(user):
    """Generate JWT token for the user."""
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
    """Authenticate the user with email and password."""
    # Find the user by email
    user = User.find_by_email(email)
    if not user or not verify_password(user.password_hash, password):
        return None  # Authentication failed
    return user


# Helper function to decode the JWT token
def decode_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def send_verification_email(email):
    """Send a verification email to the user."""
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
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {e}")
