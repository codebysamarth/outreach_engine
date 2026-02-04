"""
app/tools/gmail_tool.py
───────────────────────
Real Gmail send via langchain-google-community.

Handles OAuth credential flow (credentials.json → token.json) the
first time and caches the token for subsequent runs.
"""

from __future__ import annotations
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy-init: credentials + toolkit (avoids import errors when Gmail is not
# configured – e.g. during unit tests or CI)
# ---------------------------------------------------------------------------
_gmail_send_tool = None


def _init_gmail() -> Any:
    """Build and cache the GmailSendMessage tool."""
    global _gmail_send_tool
    if _gmail_send_tool is not None:
        return _gmail_send_tool

    from langchain_google_community.gmail.utils import (
        build_resource_service,
        get_gmail_credentials,
    )
    from langchain_google_community.gmail.send_message import GmailSendMessage

    credentials = get_gmail_credentials(
        token_file=settings.gmail.token_path,
        scopes=["https://mail.google.com/"],
        client_secrets_file=settings.gmail.credentials_path,
    )
    api_resource = build_resource_service(credentials=credentials)
    _gmail_send_tool = GmailSendMessage(api_resource=api_resource)
    logger.info("Gmail tool initialised.")
    return _gmail_send_tool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_gmail(to: str, subject: str, body: str) -> dict[str, Any]:
    """
    Send a real email via Gmail.

    Returns:
        {"status": "sent", "to": ..., "subject": ..., "message_id": ...}
        or
        {"status": "error", "error": <str>}
    """
    try:
        tool = _init_gmail()
        result = tool.invoke({
            "to":      [to],
            "subject": subject,
            "message": body,
        })
        logger.info("Gmail sent to %s – result: %s", to, result)
        return {
            "status":     "sent",
            "to":         to,
            "subject":    subject,
            "message_id": str(result),   # Gmail returns the message-id string
        }
    except Exception as exc:
        logger.error("Gmail send failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
