"""
app/tools/twilio_tool.py
────────────────────────
Real SMS send via Twilio.

Reads credentials from settings (TWILIO_ACCOUNT_SID, AUTH_TOKEN, FROM_NUMBER).
"""

from __future__ import annotations
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def send_sms(to_number: str, body: str) -> dict[str, Any]:
    """
    Send a real SMS via Twilio.

    Args:
        to_number – E.164 format, e.g. "+14155551234"
        body      – message text (keep under 160 chars for single segment)

    Returns:
        {"status": "sent", "sid": <str>, "to": <str>}
        or
        {"status": "error", "error": <str>}
    """
    if not all([
        settings.twilio.account_sid,
        settings.twilio.auth_token,
        settings.twilio.from_number,
    ]):
        logger.warning("Twilio credentials not configured – SMS not sent.")
        return {"status": "error", "error": "Twilio credentials missing in .env"}

    try:
        from twilio.rest import Client

        client = Client(settings.twilio.account_sid, settings.twilio.auth_token)
        message = client.messages.create(
            body=body,
            from_=settings.twilio.from_number,
            to=to_number,
        )
        logger.info("SMS sent to %s – SID: %s", to_number, message.sid)
        return {
            "status": "sent",
            "sid":    message.sid,
            "to":     to_number,
        }
    except Exception as exc:
        logger.error("Twilio send failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
