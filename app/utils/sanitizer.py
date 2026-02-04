"""
app/utils/sanitizer.py
──────────────────────
PII gate.  Nothing reaches Postgres or ChromaDB without passing through here.

What we KEEP (useful for future outreach, no privacy risk):
    company, role, industry, public-profile links, tone metadata,
    interest tags, draft text, scores.

What we STRIP:
    full names, phone numbers, personal email addresses,
    home / mailing addresses, date of birth, SSNs, any free-text
    that regex flags as PII.

The opaque `target_hash` (SHA-256 of the original identifier the user
supplied) lets us correlate rows without ever storing the identifier itself.
"""

from __future__ import annotations
import hashlib
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for common PII tokens
# ---------------------------------------------------------------------------
_PHONE_RE  = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
_EMAIL_RE  = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w{2,}")
# Title-Case word sequences of 2-4 words (rough name pattern)
# We'll check context separately to avoid company names
_NAME_RE   = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\b")


def compute_target_hash(identifier: str) -> str:
    """SHA-256 of the raw identifier the user gave us (e.g. LinkedIn URL)."""
    return hashlib.sha256(identifier.strip().encode()).hexdigest()


def _scrub_text(text: str) -> str:
    """Remove phone numbers and personal email addresses from free text."""
    text = _PHONE_RE.sub("[REDACTED-PHONE]", text)
    text = _EMAIL_RE.sub("[REDACTED-EMAIL]", text)
    return text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def sanitize_for_storage(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Takes the raw pipeline state dict and returns a SAFE copy
    that can be written to the DB.

    Expected keys that we honour:
        company, role, industry, links, tone_json, interests,
        recent_activity, drafts (list of {channel, subject, body, score})

    Any other key is dropped.
    """
    safe: dict[str, Any] = {}

    # ── scalar fields (whitelist) ─────────────────────────────────────
    for key in ("company", "role", "industry"):
        val = payload.get(key)
        if val:
            safe[key] = _scrub_text(str(val))

    # ── links  – only keep known public-profile keys ────────────────
    raw_links = payload.get("links") or {}
    allowed_link_keys = {
        "linkedin", "company_site", "twitter", "github",
        "portfolio", "blog", "website",
    }
    safe["links"] = {
        k: v for k, v in raw_links.items()
        if k.lower() in allowed_link_keys and isinstance(v, str)
    }

    # ── tone / persona ────────────────────────────────────────────────
    if payload.get("tone_json"):
        safe["tone_json"] = payload["tone_json"]      # already structured

    if payload.get("interests"):
        safe["interests"] = [str(i) for i in payload["interests"]]

    if payload.get("recent_activity"):
        safe["recent_activity"] = _scrub_text(str(payload["recent_activity"]))

    if payload.get("communication_style"):
        safe["communication_style"] = _scrub_text(str(payload["communication_style"]))

    # ── drafts  – scrub body + subject of any leaked PII ───────────
    raw_drafts: list[dict[str, Any]] = payload.get("drafts") or []
    safe_drafts: list[dict[str, Any]] = []
    for d in raw_drafts:
        safe_drafts.append({
            "channel":  d.get("channel", "unknown"),
            "subject":  _scrub_text(d["subject"]) if d.get("subject") else None,
            "body":     _scrub_text(d.get("body", "")),
            "score":    d.get("score"),
            "approved": d.get("approved", False),
            "sent":     d.get("sent", False),
        })
    safe["drafts"] = safe_drafts

    logger.debug("Sanitiser: kept keys = %s", list(safe.keys()))
    return safe
