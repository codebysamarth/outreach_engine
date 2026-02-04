"""
app/graph/state.py
──────────────────
The single State TypedDict that every node in the LangGraph reads from
and writes to.

Design rules:
  1. Fields are APPEND-only where possible (drafts, execution_results).
  2. "raw_*" fields are ephemeral – cleared by persona_agent after use.
  3. Nothing here is written to disk; the persistence node pulls what
     it needs, runs it through the sanitiser, then persists.

Field-by-field lifecycle
─────────────────────────
  raw_input            ingestion  →  persona  (deleted after persona)
  raw_profile_text     ingestion  →  persona  (deleted after persona)
  target_identifier    ingestion  →  persistence  (used for hashing only)
  target_hash          ingestion  →  persistence
  company / role / industry / links
                       ingestion  →  persistence
  tone                 persona    →  draft_agents
  similar_personas     persona    →  draft_agents  (context only)
  drafts               draft_agents → scoring → approval → execution → persistence
  scores               scoring    →  approval
  approved_channels    approval   →  execution
  execution_results    execution  →  persistence
  error                any node   →  persistence
"""

from __future__ import annotations
from typing import Any, TypedDict


class Draft(TypedDict):
    channel:  str               # "email" | "sms" | "linkedin" | "instagram"
    subject:  str | None        # only for email
    body:     str
    score:    float | None      # filled by scoring agent (0-10)
    approved: bool              # filled by approval node
    sent:     bool              # filled by execution node


class OutreachState(TypedDict, total=False):
    # ── ephemeral (ingestion → persona, then cleared) ─────────────────
    raw_input:           str            # whatever the user pasted in
    raw_profile_text:    str            # fetched / extracted text

    # ── stable identifiers (ingestion → persistence) ───────────────────
    target_identifier:   str            # original input (URL / email) – NOT stored in DB
    target_hash:         str            # SHA-256 of target_identifier

    # ── public business info ────────────────────────────────────────────
    company:             str
    role:                str
    industry:            str
    links:               dict[str, str] # {"linkedin": url, ...}

    # ── persona / tone (persona → drafts) ────────────────────────────────
    tone:                dict[str, Any] # structured tone dict from persona agent
    similar_personas:    list[dict[str, Any]]  # from vector DB

    # ── drafts (parallel agents → scoring → approval → execution) ───────
    drafts:              list[Draft]

    # ── approval (human-in-the-loop) ─────────────────────────────────────
    approved_channels:   list[str]      # channels the user approved

    # ── execution results ────────────────────────────────────────────────
    execution_results:   list[dict[str, Any]]

    # ── run metadata ─────────────────────────────────────────────────────
    run_id:              str
    status:              str            # mirrors OutreachRun.status
    error:               str | None
