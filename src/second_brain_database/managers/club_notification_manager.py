"""
Club Notification Manager for Second Brain Database.

Extends the existing EmailManager to provide club-specific notifications
including member invitations, event announcements, and club updates.
"""

from typing import Optional, List
from datetime import datetime, timezone

from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[ClubNotifications]")


class ClubNotificationManager:
    """
    Handles club-specific email notifications using the existing EmailManager.

    Provides notifications for:
    - Member invitations
    - Event announcements
    - Club updates
    - Role changes
    - Event reminders
    """

    def __init__(self):
        self.email_manager = email_manager
        self.logger = logger
        self._club_manager = None  # Lazy import

    @property
    def club_manager(self):
        """Lazy import of club_manager to avoid circular imports."""
        if self._club_manager is None:
            from second_brain_database.managers.club_manager import ClubManager
            self._club_manager = ClubManager()
        return self._club_manager

    async def send_club_invitation_email(
        self,
        club_id: str,
        invitee_email: str,
        inviter_username: str,
        invitation_token: str,
        club_name: str,
        club_description: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> bool:
        """
        Send club membership invitation email.

        Args:
            club_id: Club ID
            invitee_email: Email of person being invited
            inviter_username: Username of person sending invitation
            invitation_token: Unique invitation token
            club_name: Name of the club
            club_description: Optional club description
            expires_at: Optional expiration date string

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Build invitation URLs
            base_url = settings.BASE_URL or "http://localhost:3000"
            accept_url = f"{base_url}/clubs/{club_id}/invitations/{invitation_token}/accept"
            decline_url = f"{base_url}/clubs/{club_id}/invitations/{invitation_token}/decline"

            subject = f"Club Invitation: {club_name}"

            # Build HTML content
            html_content = f"""
            <html>
            <head>
                <style>
                    .club-card {{
                        border: 1px solid #e0e0e0;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 20px 0;
                        background-color: #f9f9f9;
                    }}
                    .action-button {{
                        display: inline-block;
                        padding: 12px 24px;
                        margin: 10px 5px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: bold;
                    }}
                    .accept-button {{
                        background-color: #4CAF50;
                        color: white;
                    }}
                    .decline-button {{
                        background-color: #f44336;
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <h2>Club Invitation</h2>

                <p>Hello!</p>

                <p><strong>@{inviter_username}</strong> has invited you to join the club <strong>{club_name}</strong>.</p>

                <div class="club-card">
                    <h3>{club_name}</h3>
                    {f'<p>{club_description}</p>' if club_description else ''}
                    <p><em>Club ID: {club_id}</em></p>
                </div>

                <p>Click below to respond to this invitation:</p>

                <p>
                    <a href="{accept_url}" class="action-button accept-button">Accept Invitation</a>
                    <a href="{decline_url}" class="action-button decline-button">Decline Invitation</a>
                </p>

                {f'<p><small>This invitation expires on {expires_at}.</small></p>' if expires_at else ''}

                <p>If you did not expect this invitation, you can safely ignore this email.</p>

                <hr>
                <p><small>This invitation was sent by the Second Brain Database Club Management System.</small></p>
            </body>
            </html>
            """

            self.logger.info(f"Sending club invitation email to {invitee_email} for club {club_name}")

            return await self.email_manager.send_html_email(
                to_email=invitee_email,
                subject=subject,
                html_content=html_content,
                username=invitee_email
            )

        except Exception as e:
            self.logger.error(f"Failed to send club invitation email: {e}", exc_info=True)
            return False

    async def send_event_announcement_email(
        self,
        club_id: str,
        event_title: str,
        event_description: str,
        event_date: str,
        event_location: str,
        recipient_emails: List[str],
        organizer_username: str,
        rsvp_link: Optional[str] = None,
    ) -> bool:
        """
        Send event announcement email to club members.

        Args:
            club_id: Club ID
            event_title: Title of the event
            event_description: Description of the event
            event_date: Date/time of the event
            event_location: Location (could be physical or virtual room)
            recipient_emails: List of emails to send to
            organizer_username: Username of event organizer
            rsvp_link: Optional RSVP link

        Returns:
            bool: True if all emails sent successfully
        """
        try:
            subject = f"Club Event: {event_title}"

            # Build RSVP section
            rsvp_section = ""
            if rsvp_link:
                rsvp_section = f"""
                <p>
                    <a href="{rsvp_link}" style="background-color: #2196F3; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">RSVP Now</a>
                </p>
                """

            html_content = f"""
            <html>
            <head>
                <style>
                    .event-card {{
                        border: 1px solid #e0e0e0;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 20px 0;
                        background-color: #f9f9f9;
                    }}
                    .event-details {{
                        margin: 10px 0;
                    }}
                    .action-button {{
                        display: inline-block;
                        padding: 12px 24px;
                        margin: 10px 5px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: bold;
                    }}
                </style>
            </head>
            <body>
                <h2>Club Event Announcement</h2>

                <div class="event-card">
                    <h3>{event_title}</h3>
                    <div class="event-details">
                        <p><strong>Date:</strong> {event_date}</p>
                        <p><strong>Location:</strong> {event_location}</p>
                        <p><strong>Organized by:</strong> @{organizer_username}</p>
                    </div>
                    <p>{event_description}</p>
                </div>

                {rsvp_section}

                <p>We look forward to seeing you there!</p>

                <hr>
                <p><small>This announcement was sent by the Second Brain Database Club Management System.</small></p>
            </body>
            </html>
            """

            success_count = 0
            for email in recipient_emails:
                try:
                    # Use the email manager's console provider for development
                    # In production, this would use real email providers
                    success = await self.email_manager.send_html_email(
                        to_email=email,
                        subject=subject,
                        html_content=html_content,
                        username=email
                    )
                    if success:
                        success_count += 1
                    else:
                        self.logger.warning(f"Failed to send event announcement to {email}")

                except Exception as e:
                    self.logger.error(f"Error sending event announcement to {email}: {e}")

            total_recipients = len(recipient_emails)
            self.logger.info(f"Sent event announcement to {success_count}/{total_recipients} recipients")

            return success_count == total_recipients

        except Exception as e:
            self.logger.error(f"Failed to send event announcement emails: {e}", exc_info=True)
            return False

    async def send_role_change_notification_email(
        self,
        club_id: str,
        user_email: str,
        username: str,
        old_role: str,
        new_role: str,
        changed_by_username: str,
        club_name: str,
    ) -> bool:
        """
        Send role change notification email.

        Args:
            club_id: Club ID
            user_email: Email of user whose role changed
            username: Username of user whose role changed
            old_role: Previous role
            new_role: New role
            changed_by_username: Username of person who made the change
            club_name: Name of the club

        Returns:
            bool: True if email sent successfully
        """
        try:
            subject = f"Club Role Update: {club_name}"

            html_content = f"""
            <html>
            <body>
                <h2>Club Role Update</h2>

                <p>Hello @{username},</p>

                <p>Your role in <strong>{club_name}</strong> has been updated:</p>

                <div style="background-color: #f0f8ff; padding: 15px; border-radius: 6px; margin: 15px 0;">
                    <p><strong>Previous Role:</strong> {old_role.title()}</p>
                    <p><strong>New Role:</strong> {new_role.title()}</p>
                    <p><strong>Changed by:</strong> @{changed_by_username}</p>
                </div>

                <p>If you have any questions about your new role and responsibilities, please contact the club administrators.</p>

                <hr>
                <p><small>This notification was sent by the Second Brain Database Club Management System.</small></p>
            </body>
            </html>
            """

            self.logger.info(f"Sending role change notification to {user_email} for club {club_name}")

            return await self.email_manager.send_html_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                username=username
            )

        except Exception as e:
            self.logger.error(f"Failed to send role change notification: {e}", exc_info=True)
            return False

    async def send_event_reminder_email(
        self,
        club_id: str,
        event_title: str,
        event_date: str,
        event_location: str,
        recipient_emails: List[str],
        club_name: str,
        hours_until_event: int,
    ) -> bool:
        """
        Send event reminder email.

        Args:
            club_id: Club ID
            event_title: Title of the event
            event_date: Date/time of the event
            event_location: Location of the event
            recipient_emails: List of emails to send to
            club_name: Name of the club
            hours_until_event: Hours until event starts

        Returns:
            bool: True if all emails sent successfully
        """
        try:
            subject = f"Event Reminder: {event_title} - {hours_until_event} hours"

            html_content = f"""
            <html>
            <body>
                <h2>Event Reminder</h2>

                <p>This is a reminder for an upcoming club event:</p>

                <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin: 20px 0; background-color: #fff8e1;">
                    <h3>{event_title}</h3>
                    <p><strong>Club:</strong> {club_name}</p>
                    <p><strong>Date:</strong> {event_date}</p>
                    <p><strong>Location:</strong> {event_location}</p>
                    <p><strong>Time until event:</strong> {hours_until_event} hours</p>
                </div>

                <p>Don't forget to attend!</p>

                <hr>
                <p><small>This reminder was sent by the Second Brain Database Club Management System.</small></p>
            </body>
            </html>
            """

            success_count = 0
            for email in recipient_emails:
                try:
                    success = await self.email_manager.send_html_email(
                        to_email=email,
                        subject=subject,
                        html_content=html_content,
                        username=email
                    )
                    if success:
                        success_count += 1

                except Exception as e:
                    self.logger.error(f"Error sending event reminder to {email}: {e}")

            total_recipients = len(recipient_emails)
            self.logger.info(f"Sent event reminder to {success_count}/{total_recipients} recipients")

            return success_count == total_recipients

        except Exception as e:
            self.logger.error(f"Failed to send event reminder emails: {e}", exc_info=True)
            return False


# Singleton instance
club_notification_manager = ClubNotificationManager()