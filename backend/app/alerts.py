import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("alerts")


def send_conjunction_alert(to_email: str, name_1: str, name_2: str, distance_km: float) -> bool:
    subject = f"Close approach alert: {name_1} <-> {name_2}"
    body = (
        f"Your tracked satellite is involved in a close approach.\n\n"
        f"Object 1: {name_1}\n"
        f"Object 2: {name_2}\n"
        f"Predicted separation: {distance_km:.2f} km\n\n"
        f"View live details on your dashboard."
    )

    if not settings.smtp_host:
        logger.info("SMTP not configured — skipping email, would have sent: %s", subject)
        return False

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [to_email], message.as_string())
        return True
    except Exception as exc:
        logger.warning("Failed to send alert email to %s: %s", to_email, exc)
        return False
