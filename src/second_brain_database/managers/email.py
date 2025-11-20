"""
EmailManager module for Second Brain Database.

- This module provides the EmailManager class,
which handles sending emails using multiple providers (SMTP, Mailgun, SendGrid, etc.).
- It supports sending HTML emails for verification and other purposes,
and is fully instrumented with production-grade logging.
"""

from typing import Optional

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[EmailManager]")


class EmailManager:
    """
    Handles sending emails using multiple providers (SMTP, Mailgun, SendGrid, etc.).
    Supports sending HTML emails for verification and other purposes.
    """

    def __init__(self):
        self.logger = logger
        # Placeholder for provider configs (add as needed)
        self.providers = [self._send_via_console]  # Add real providers here
        self.logger.debug("Initialized with providers: %s", [p.__name__ for p in self.providers])

    async def send_verification_email(
        self, to_email: str, verification_link: str, username: Optional[str] = None
    ) -> bool:
        """
        Send a verification email to the specified address using available providers.
        Returns True if sent successfully, False otherwise.
        """
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
        self.logger.info("Attempting to send verification email to %s (username=%s)", to_email, username)
        for provider in self.providers:
            try:
                self.logger.debug("Trying provider: %s for %s", provider.__name__, to_email)
                await provider(to_email, subject, html_content)
                self.logger.info("Verification email sent to %s using provider %s", to_email, provider.__name__)
                return True
            except RuntimeError as e:
                self.logger.warning(
                    "Email provider %s failed for %s: %s", provider.__name__, to_email, e, exc_info=True
                )
        self.logger.error("All email providers failed to send verification to %s", to_email, exc_info=True)
        return False

    async def send_family_invitation_email(
        self,
        to_email: str,
        inviter_username: str,
        family_name: str,
        relationship_type: str,
        accept_link: str,
        decline_link: str,
        expires_at: str,
    ) -> bool:
        """
        Send a family invitation email to the specified address.
        Returns True if sent successfully, False otherwise.
        """
        subject = f"Family Invitation from {inviter_username}"
        html_content = f"""
        <html>
        <body>
            <h2>Family Invitation</h2>
            <p>Hey there! You are invited by @{inviter_username} to join {family_name} as their {relationship_type}.</p>
            <p>
                <a href='{accept_link}' style='background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;'>Accept Invitation</a>
                <a href='{decline_link}' style='background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-left: 10px;'>Decline Invitation</a>
            </p>
            <p>This invitation will expire on {expires_at}.</p>
            <p>If you did not expect this invitation, you can safely ignore this email.</p>
        </body>
        </html>
        """
        self.logger.info("Attempting to send family invitation email to %s from %s", to_email, inviter_username)
        for provider in self.providers:
            try:
                self.logger.debug("Trying provider: %s for family invitation to %s", provider.__name__, to_email)
                await provider(to_email, subject, html_content)
                self.logger.info("Family invitation email sent to %s using provider %s", to_email, provider.__name__)
                return True
            except RuntimeError as e:
                self.logger.warning(
                    "Email provider %s failed for family invitation to %s: %s",
                    provider.__name__,
                    to_email,
                    e,
                    exc_info=True,
                )
        self.logger.error("All email providers failed to send family invitation to %s", to_email, exc_info=True)
        return False

    async def send_html_email(
        self, to_email: str, subject: str, html_content: str, username: Optional[str] = None
    ) -> bool:
        """
        Send an HTML email with custom subject and content.
        Returns True if sent successfully, False otherwise.
        """
        self.logger.info("Attempting to send HTML email to %s (username=%s)", to_email, username)
        for provider in self.providers:
            try:
                self.logger.debug("Trying provider: %s for %s", provider.__name__, to_email)
                await provider(to_email, subject, html_content)
                self.logger.info("HTML email sent to %s using provider %s", to_email, provider.__name__)
                return True
            except RuntimeError as e:
                self.logger.warning(
                    "Email provider %s failed for %s: %s", provider.__name__, to_email, e, exc_info=True
                )
        self.logger.error("All email providers failed to send HTML email to %s", to_email, exc_info=True)
        return False

    async def _send_via_console(self, to_email: str, subject: str, html_content: str) -> None:
        """
        For development: log the email and print to console instead of sending.
        """
        self.logger.info("[DEV EMAIL] To: %s\nSubject: %s\nHTML:\n%s", to_email, subject, html_content)
        self.logger.debug("Email content for %s: subject=%s, html_length=%d", to_email, subject, len(html_content))
        print(f"\n[DEV EMAIL] To: {to_email}\nSubject: {subject}\nHTML:\n{html_content}\n")


# Singleton instance
email_manager = EmailManager()
