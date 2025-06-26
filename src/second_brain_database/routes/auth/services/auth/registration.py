from datetime import datetime
from fastapi import HTTPException, status
import bcrypt
import secrets
from second_brain_database.routes.auth.models import UserIn, validate_password_strength
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

async def register_user(user: UserIn):
    """Register a new user, validate password, and return user doc and verification token."""
    if not validate_password_strength(user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
                   "uppercase, lowercase, digit, and special character"
        )
    existing_user = await db_manager.get_collection("users").find_one({
        "$or": [
            {"username": user.username},
            {"email": user.email}
        ]
    })
    if existing_user:
        # Generic error to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    hashed_pw = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    verification_token = secrets.token_urlsafe(32)
    user_doc = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_pw,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "failed_login_attempts": 0,
        "last_login": None,
        "is_verified": False,
        "verification_token": verification_token,
        "plan": user.plan,
        "team": user.team,
        "role": user.role,
        "client_side_encryption": user.client_side_encryption
    }
    result = await db_manager.get_collection("users").insert_one(user_doc)
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    return user_doc, verification_token


async def send_welcome_email(email: str, username: str = None):
    """Send a personalized welcome email after user verifies their email."""
    subject = "Welcome to Second Brain Database!"
    display_name = username or "there"
    html_content = f"""
    <html><body>
    <h2>Hey {display_name}, welcome and thank you for verifying your email!</h2>
    <p>We’re excited to have you join the Second Brain Database community. Your account is now fully active, and you can start exploring all the features we offer to help you organize, secure, and supercharge your knowledge.</p>
    <p>If you have any questions or need assistance, our team is here to help. Wishing you a productive and inspiring journey with us!</p>
    <br>
    <p>Best regards,<br>The Second Brain Database Team</p>
    </body></html>
    """
    logger.info(f"[WELCOME EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)


async def verify_user_email(token: str):
    """Verify a user's email using the provided token and send a welcome email."""
    user = await db_manager.get_collection("users").find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
    )
    # Send welcome email after successful verification
    await send_welcome_email(user["email"], user.get("username"))
    return user


async def send_account_suspension_email(email: str, username: str = None):
    """
    Optionally notify the user by email when their account is suspended for abuse.
    """
    subject = "Account Suspended Due to Abuse"
    display_name = username or "user"
    html_content = f"""
    <html><body>
    <h2>Account Suspended</h2>
    <p>Dear {display_name},</p>
    <p>Your account has been suspended due to repeated abuse of the password reset system. If you believe this is a mistake, please contact support for review and possible reactivation.</p>
    <p>Thank you,<br>The Second Brain Database Team</p>
    </body></html>
    """
    logger.info(f"[SUSPEND EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)

