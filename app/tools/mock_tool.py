"""
app/tools/mock_tool.py
──────────────────────
Mock send for channels that don't have a real API wired up yet
(LinkedIn DM, Instagram DM).

Logs the payload so you can see exactly what would be sent,
and returns the same shape as the real tools so the execution
agent doesn't need any if/else branches.
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def mock_send(channel: str, to: str, body: str, subject: str | None = None) -> dict[str, Any]:
    """
    Simulate sending a message on an unsupported channel.

    Prints a clearly labelled block to the console so the user can
    copy-paste the draft into the real app manually if they want.

    Returns the same dict shape as gmail_tool / twilio_tool.
    """
    separator = "=" * 60
    logger.info(separator)
    logger.info("  [MOCK SEND] Channel  : %s", channel.upper())
    logger.info("  [MOCK SEND] To       : %s", to)
    if subject:
        logger.info("  [MOCK SEND] Subject  : %s", subject)
    logger.info("  [MOCK SEND] Body     :")
    for line in body.splitlines():
        logger.info("                %s", line)
    logger.info(separator)

    # Also print to stdout so it's visible even if logging goes to file
    print(f"\n{separator}")
    print(f"  [MOCK – {channel.upper()}]")
    print(f"  To      : {to}")
    if subject:
        print(f"  Subject : {subject}")
    print(f"  Body    :\n{body}")
    print(separator, end="\n\n")

    return {
        "status":  "mock_sent",
        "channel": channel,
        "to":      to,
    }
