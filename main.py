#!/usr/bin/env python3
"""
main.py
───────
CLI entry-point for the Outreach Engine.

Usage:
    python main.py                          # interactive mode – prompts for input
    python main.py --input "https://..."    # single-shot with a URL or text
    python main.py --input-file targets.txt # batch mode – one target per line

The script:
  1. Validates the environment (Ollama reachable, etc.)
  2. Builds the LangGraph workflow
  3. Invokes it with the user's input
  4. Pretty-prints each stage as it completes
  5. Handles the approval / regen loop inline
"""

from __future__ import annotations
import argparse
import logging
import sys
import textwrap
import time
from typing import Any

# ---------------------------------------------------------------------------
# Logging setup (before any app imports that might log at import time)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("outreach_engine")

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          🚀  OUTREACH ENGINE  –  Cold Outreach AI           ║
║     LangChain + LangGraph + Local Ollama + Postgres         ║
╚══════════════════════════════════════════════════════════════╝
"""


# ===========================================================================
# Pre-flight checks
# ===========================================================================

def check_ollama() -> bool:
    """Ping the Ollama HTTP API to make sure it's running."""
    import requests
    from app.config import settings
    try:
        resp = requests.get(f"{settings.ollama.base_url}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if settings.ollama.model not in models:
            logger.warning(
                "Model '%s' not found in Ollama. Available: %s\n"
                "Pull it with:  ollama pull %s",
                settings.ollama.model, models, settings.ollama.model,
            )
            return False
        logger.info("✓ Ollama OK – model '%s' available.", settings.ollama.model)
        return True
    except Exception as exc:
        logger.error(
            "✗ Cannot reach Ollama at %s: %s\n"
            "  Start it with:  docker compose up -d ollama",
            settings.ollama.base_url, exc,
        )
        return False


def check_chromadb() -> bool:
    """Ping ChromaDB."""
    import requests
    from app.config import settings
    try:
        resp = requests.get(f"http://{settings.chroma.host}:{settings.chroma.port}/api/v1/heartbeat", timeout=3)
        resp.raise_for_status()
        logger.info("✓ ChromaDB OK.")
        return True
    except Exception as exc:
        logger.warning("✗ ChromaDB not reachable: %s  (vector similarity will be empty)", exc)
        return False


def check_postgres() -> bool:
    """Try a quick sync connect to Postgres."""
    try:
        import psycopg2
        from app.config import settings
        conn = psycopg2.connect(
            host=settings.postgres.host,
            port=settings.postgres.port,
            dbname=settings.postgres.db,
            user=settings.postgres.user,
            password=settings.postgres.password,
            connect_timeout=3,
        )
        conn.close()
        logger.info("✓ Postgres OK.")
        return True
    except Exception as exc:
        logger.warning("✗ Postgres not reachable: %s  (persistence will fail at the end)", exc)
        return False


# ===========================================================================
# Pretty-print helpers
# ===========================================================================

def print_stage(name: str) -> None:
    print(f"\n{'═' * 58}")
    print(f"  ▶  {name}")
    print(f"{'═' * 58}")


def print_drafts(drafts: list[dict]) -> None:
    for i, d in enumerate(drafts, 1):
        score_str = f"{d.get('score')}/10" if d.get("score") is not None else "N/A"
        print(f"\n  ┌─── [{i}] {d['channel'].upper()}  |  Score: {score_str} ───")
        if d.get("subject"):
            print(f"  │  Subject : {d['subject']}")
        for line in d["body"].splitlines():
            print(f"  │  {line}")
        print(f"  └{'─' * 50}")


# ===========================================================================
# Approval / Regen loop  (inline – works without langgraph interrupt)
# ===========================================================================

def run_approval_loop(graph: Any, state: dict) -> dict:
    """
    Invoke scoring → approval → (regen → scoring → approval)* → execution → persistence.

    This drives the graph node-by-node through the approval section so we
    can intercept and display drafts at each iteration.
    """
    from app.agents.scoring_agent               import scoring_node
    from app.agents.approval_and_persistence    import approval_node, persistence_node
    from app.agents.execution_agent             import execution_node
    from app.agents.draft_agents                import _generate_draft

    MAX_REGEN = 3
    regen_round = 0

    while True:
        # ── Score ──────────────────────────────────────────────────
        print_stage("SCORING")
        state = scoring_node(state)

        # ── Display drafts ─────────────────────────────────────────
        print_stage("HUMAN APPROVAL")
        drafts = state.get("drafts", [])
        print_drafts(drafts)

        print("\n  For each draft choose:  approve | regen | skip")
        print("  Example:  email=approve sms=regen linkedin=approve instagram=skip\n")
        raw = input("  >>> ").strip()

        approved: list[str] = []
        regen:    list[str] = []
        for token in raw.split():
            if "=" not in token:
                continue
            ch, choice = token.split("=", 1)
            ch, choice = ch.strip().lower(), choice.strip().lower()
            if choice == "approve":
                approved.append(ch)
            elif choice == "regen":
                regen.append(ch)

        # Mark approved
        updated_drafts = []
        for d in drafts:
            updated_drafts.append({**d, "approved": (d["channel"] in approved)})
        state = {**state, "drafts": updated_drafts, "approved_channels": approved}

        # ── Regen? ─────────────────────────────────────────────────
        if regen:
            regen_round += 1
            if regen_round > MAX_REGEN:
                print(f"\n  ⚠  Max regen rounds ({MAX_REGEN}) reached. Skipping regen.")
            else:
                print_stage(f"REGENERATING: {[c.upper() for c in regen]}  (round {regen_round}/{MAX_REGEN})")
                new_drafts = []
                for d in state["drafts"]:
                    if d["channel"] in regen:
                        new_drafts.append(_generate_draft(d["channel"], state))
                    else:
                        new_drafts.append(d)
                state = {**state, "drafts": new_drafts}
                continue           # loop back to scoring

        break                       # no regen – proceed

    # ── Execute ────────────────────────────────────────────────────
    print_stage("EXECUTION")
    state = execution_node(state)

    # Print execution results
    for r in state.get("execution_results", []):
        status = r.get("status", "unknown")
        ch     = r.get("channel", "?")
        print(f"  [{ch.upper()}]  status={status}  {r}")

    # ── Persist ────────────────────────────────────────────────────
    print_stage("PERSISTENCE")
    state = persistence_node(state)

    return state


# ===========================================================================
# Main
# ===========================================================================

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="Outreach Engine CLI")
    parser.add_argument("--input",      type=str,  default=None, help="Target info (URL or text)")
    parser.add_argument("--input-file", type=str,  default=None, help="File with one target per line")
    parser.add_argument("--skip-checks",action="store_true",     help="Skip pre-flight checks")
    args = parser.parse_args()

    # ── Pre-flight ─────────────────────────────────────────────────
    if not args.skip_checks:
        print_stage("PRE-FLIGHT CHECKS")
        check_ollama()
        check_chromadb()
        check_postgres()

    # ── Collect targets ─────────────────────────────────────────────
    targets: list[str] = []

    if args.input_file:
        with open(args.input_file) as f:
            targets = [line.strip() for line in f if line.strip()]
    elif args.input:
        targets = [args.input]
    else:
        print("  Paste target info below (LinkedIn URL, text, or a mix).")
        print("  Press Enter on an empty line when done.\n")
        lines: list[str] = []
        while True:
            line = input("  > ")
            if not line:
                break
            lines.append(line)
        targets = ["\n".join(lines)]

    if not targets:
        print("  No targets provided. Exiting.")
        sys.exit(0)

    # ── Build graph (only the first two nodes run via graph.invoke;
    #    the rest are driven by run_approval_loop for CLI interactivity) ─
    from app.agents.ingestion_agent import ingestion_node
    from app.agents.persona_agent   import persona_node
    from app.agents.draft_agents    import (
        draft_email_node, draft_sms_node,
        draft_linkedin_node, draft_instagram_node,
    )

    # ── Process each target ────────────────────────────────────────
    for idx, target in enumerate(targets, 1):
        print(f"\n\n{'█' * 58}")
        print(f"  TARGET {idx}/{len(targets)}")
        print(f"{'█' * 58}")

        # ── Initial state ──────────────────────────────────────────
        state: dict = {"raw_input": target}

        # ── INGESTION ──────────────────────────────────────────────
        print_stage("INGESTION")
        state = ingestion_node(state)
        print(f"  company  = {state.get('company')}")
        print(f"  role     = {state.get('role')}")
        print(f"  industry = {state.get('industry')}")
        print(f"  links    = {state.get('links')}")

        # ── PERSONA ────────────────────────────────────────────────
        print_stage("PERSONA ANALYSIS")
        state = persona_node(state)
        tone = state.get("tone", {})
        print(f"  formality        = {tone.get('formality_level')}")
        print(f"  style            = {tone.get('communication_style')}")
        print(f"  language_hints   = {tone.get('language_hints')}")
        print(f"  interests        = {tone.get('interests')}")
        print(f"  tone_keywords    = {tone.get('tone_keywords')}")

        # ── PARALLEL DRAFTS ────────────────────────────────────────
        print_stage("GENERATING DRAFTS (parallel)")
        # Run all four; in production these would be truly parallel threads.
        # For the CLI we run sequentially but the graph wiring supports parallel.
        state = draft_email_node(state)
        state = draft_sms_node(state)
        state = draft_linkedin_node(state)
        state = draft_instagram_node(state)

        # ── APPROVAL LOOP (scoring → approval → regen? → execution → persist) ─
        state = run_approval_loop(None, state)

        print_stage("DONE ✓")
        print(f"  Status: {state.get('status')}")
        print()


if __name__ == "__main__":
    main()
