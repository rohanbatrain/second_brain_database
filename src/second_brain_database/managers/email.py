"""
EmailManager module for Second Brain Database.

- This module provides the EmailManager class,
which handles sending emails using multiple providers (SMTP, Mailgun, SendGrid, etc.).
- It supports sending HTML emails for verification and other purposes,
and is fully instrumented with production-grade logging.
"""
from typing import Optional
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

class EmailManager:
    """
    Handles sending emails using multiple providers (SMTP, Mailgun, SendGrid, etc.).
    Supports sending HTML emails for verification and other purposes.
    """
    def __init__(self):
        self.logger = logger
        # Placeholder for provider configs (add as needed)
        self.providers = [self._send_via_console]  # Add real providers here
        self.logger.debug("[EmailManager] Initialized with providers: %s", [p.__name__ for p in self.providers])

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
        self.logger.info(
            "[EmailManager] Attempting to send verification email to %s (username=%s)", to_email, username
        )
        for provider in self.providers:
            try:
                self.logger.debug("[EmailManager] Trying provider: %s for %s", provider.__name__, to_email)
                await provider(to_email, subject, html_content)
                self.logger.info(
                    "[EmailManager] Verification email sent to %s using provider %s", to_email, provider.__name__
                )
                return True
            except RuntimeError as e:
                self.logger.warning(
                    "[EmailManager] Email provider %s failed for %s: %s",
                    provider.__name__, to_email, e, exc_info=True
                )
        self.logger.error(
            "[EmailManager] All email providers failed to send verification to %s", to_email, exc_info=True
        )
        return False

    async def _send_via_console(self, to_email: str, subject: str, html_content: str) -> None:
        """
        For development: log the email instead of sending.
        """
        self.logger.info(
            "[EmailManager] [DEV EMAIL] To: %s\nSubject: %s\nHTML:\n%s", to_email, subject, html_content
        )
        self.logger.debug(
            "[EmailManager] Email content for %s: subject=%s, html_length=%d", to_email, subject, len(html_content)
        )

# Singleton instance
email_manager = EmailManager()