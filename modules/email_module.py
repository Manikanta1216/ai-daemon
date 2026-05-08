"""
JARVIS AI — Email Module
Handles sending emails via SMTP.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("jarvis.modules.email")


def send_email(
    recipient: str,
    subject: str = None,
    body: str = "",
    **kwargs,
) -> str:
    """Send an email via SMTP."""
    from config import SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD

    if not SMTP_EMAIL or not SMTP_PASSWORD or SMTP_PASSWORD == "your_app_password":
        return (
            "Email is not configured. "
            "Set SMTP_EMAIL and SMTP_PASSWORD in your .env file."
        )

    if not recipient:
        return "No recipient specified."

    # Auto-generate subject if not provided
    if not subject:
        subject = f"Message from JARVIS - {body[:50]}" if body else "Message from JARVIS"

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, recipient, msg.as_string())

        logger.info(f"Email sent to {recipient}")
        return f"Email sent successfully to {recipient}"

    except smtplib.SMTPAuthenticationError:
        return (
            "Email authentication failed. "
            "Make sure you're using an App Password, not your regular password."
        )
    except Exception as e:
        logger.error(f"Email error: {e}")
        return f"Failed to send email: {e}"


# Module capabilities
CAPABILITIES = {
    "send_email": {
        "handler": lambda entities: send_email(
            recipient=entities.get("recipient", ""),
            subject=entities.get("subject"),
            body=entities.get("body", ""),
        ),
        "description": "Send an email via SMTP",
    },
}
