"""
app/db/models.py
────────────────
SQLAlchemy ORM models.

PII POLICY (enforced here):
  – No full names, phone numbers, personal emails, or home addresses.
  – We store:
      • A hashed, opaque `target_id` (SHA-256 of email/LinkedIn URL)
        so we can reference the same target again without storing the PII.
      • Company, role, industry  – public business info.
      • Tone metadata, important links, drafts, scores.
      • Timestamps for audit / TTL.

  The sanitizer (app/utils/sanitizer.py) is the gate that produces
  the payload that lands here.
"""

from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Float,
    DateTime, Boolean, ForeignKey, JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# TargetProfile  –  one row per unique outreach target
# ---------------------------------------------------------------------------
class TargetProfile(Base):
    __tablename__ = "target_profiles"

    id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Opaque hash so we can match repeat targets without PII
    target_hash: str = Column(String(64), unique=True, nullable=False, index=True)

    # ── public / business info (NOT personal) ──────────────────────────
    company:  str | None = Column(String(255), nullable=True)
    role:     str | None = Column(String(255), nullable=True)
    industry: str | None = Column(String(255), nullable=True)

    # ── important links (public profiles – no auth tokens) ─────────────
    links: dict | None = Column(JSON, nullable=True)
    # example:  {"linkedin": "https://linkedin.com/in/xxx",
    #            "company_site": "https://acme.com"}

    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── relationships ────────────────────────────────────────────────────
    persona  = relationship("PersonaRecord",  back_populates="target", uselist=False)
    drafts   = relationship("DraftRecord",    back_populates="target")
    runs     = relationship("OutreachRun",    back_populates="target")


# ---------------------------------------------------------------------------
# PersonaRecord  –  derived tone / style analysis (no raw profile text)
# ---------------------------------------------------------------------------
class PersonaRecord(Base):
    __tablename__ = "persona_records"

    id:        uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: uuid.UUID = Column(PG_UUID(as_uuid=True), ForeignKey("target_profiles.id"), unique=True, nullable=False)

    # ── tone metadata ────────────────────────────────────────────────────
    formality_level:  str | None = Column(String(20), nullable=True)   # casual | semi-formal | formal
    communication_style: str | None = Column(String(500), nullable=True)
    language_hints:   str | None = Column(Text, nullable=True)         # e.g. "uses emojis, short sentences"
    interests:        list | None = Column(JSON, nullable=True)        # ["AI", "startups", ...]
    recent_activity:  str | None = Column(Text, nullable=True)         # summary only, no PII

    # full structured tone JSON produced by persona_agent
    tone_json: dict | None = Column(JSON, nullable=True)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    target = relationship("TargetProfile", back_populates="persona")


# ---------------------------------------------------------------------------
# DraftRecord  –  one row per channel per run
# ---------------------------------------------------------------------------
class DraftRecord(Base):
    __tablename__ = "draft_records"

    id:        uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: uuid.UUID = Column(PG_UUID(as_uuid=True), ForeignKey("target_profiles.id"), nullable=False)
    run_id:    uuid.UUID = Column(PG_UUID(as_uuid=True), ForeignKey("outreach_runs.id"), nullable=False)

    channel:   str = Column(String(30), nullable=False)        # email | sms | linkedin | instagram
    subject:   str | None = Column(String(255), nullable=True) # only for email
    body:      str = Column(Text, nullable=False)
    score:     float | None = Column(Float, nullable=True)     # 0-10 from scoring agent
    approved:  bool = Column(Boolean, default=False)
    sent:      bool = Column(Boolean, default=False)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    target = relationship("TargetProfile", back_populates="drafts")
    run    = relationship("OutreachRun",    back_populates="drafts")


# ---------------------------------------------------------------------------
# OutreachRun  –  one row per full pipeline execution
# ---------------------------------------------------------------------------
class OutreachRun(Base):
    __tablename__ = "outreach_runs"

    id:        uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: uuid.UUID = Column(PG_UUID(as_uuid=True), ForeignKey("target_profiles.id"), nullable=False)

    status: str = Column(String(30), default="pending")
    # pending | persona_done | drafts_done | scored | approved | executed | failed

    error_message: str | None = Column(Text, nullable=True)

    started_at:  datetime       = Column(DateTime, default=datetime.utcnow)
    completed_at: datetime | None = Column(DateTime, nullable=True)

    target = relationship("TargetProfile", back_populates="runs")
    drafts = relationship("DraftRecord",    back_populates="run")
