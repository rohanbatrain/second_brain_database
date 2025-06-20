import logging
from typing import Optional

class EmailManager:
    """
    Handles sending emails using multiple providers (SMTP, Mailgun, SendGrid, etc.).
    Supports sending HTML emails for verification and other purposes.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Placeholder for provider configs (add as needed)
        self.providers = [self._send_via_console]  # Add real providers here

    async def send_verification_email(self, to_email: str, verification_link: str, username: Optional[str] = None):
        subject = "Verify your email address"
        html_content = f"""
        <html>
        <body>
            <h2>Welcome{f' {username}' if username else ''}!</h2>
            <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
            <a href='{verification_link}'>Verify Email</a>
            <p>If you did not register, you can ignore this email.</p>
        </body>
        </html>
        """
        for provider in self.providers:
            try:
                await provider(to_email, subject, html_content)
                return True
            except Exception as e:
                self.logger.warning(f"Email provider failed: {e}")
        self.logger.error(f"All email providers failed to send verification to {to_email}")
        return False

    async def _send_via_console(self, to_email, subject, html_content):
        # For development: log the email instead of sending
        self.logger.info(f"[DEV EMAIL] To: {to_email}\nSubject: {subject}\nHTML:\n{html_content}")

# Singleton instance
email_manager = EmailManager()