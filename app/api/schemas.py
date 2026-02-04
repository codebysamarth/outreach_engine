"""
app/api/schemas.py
──────────────────
Pydantic request/response models for the API.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────────────────

class CampaignStartRequest(BaseModel):
    """Request to start a new outreach campaign."""
    input_type: str = Field(..., description="'url', 'text', or 'file'")
    content: str = Field(..., description="URL, text, or file path")


class DraftActionRequest(BaseModel):
    """Request to approve/regen/skip a draft."""
    action: str = Field(..., description="'approve', 'regen', or 'skip'")


# ── Response schemas ───────────────────────────────────────────────────────

class DraftResponse(BaseModel):
    """Single draft channel response."""
    channel: str
    subject: str | None = None
    body: str
    score: float | None = None
    approved: bool = False


class StageUpdate(BaseModel):
    """Real-time stage progress update."""
    stage: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CampaignResponse(BaseModel):
    """Campaign status and results."""
    campaign_id: str
    status: str
    current_stage: str
    target_company: str | None = None
    target_role: str | None = None
    drafts: list[DraftResponse] = []
    error: str | None = None
