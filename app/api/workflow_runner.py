"""
app/api/workflow_runner.py
──────────────────────────
Async wrapper for running LangGraph workflows with real-time updates.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any

from app.graph.workflow import build_graph
from app.api.state_manager import state_manager

logger = logging.getLogger(__name__)


async def run_campaign_workflow(campaign_id: str, raw_input: str):
    """
    Run the full LangGraph workflow asynchronously with stage updates.
    """
    try:
        # Build the graph
        graph = build_graph().compile()
        
        # Initial state
        initial_state = {"raw_input": raw_input}
        
        # Stage mapping
        stage_map = {
            "ingestion": "ingestion",
            "persona": "persona",
            "draft_email": "drafting",
            "draft_sms": "drafting",
            "draft_linkedin": "drafting",
            "draft_instagram": "drafting",
            "scoring": "scoring",
            "approval": "approval",
            "execution": "execution",
            "persistence": "persistence",
        }
        
        current_drafting = False
        
        # Stream through the workflow
        async for event in graph.astream(initial_state):
            logger.info(f"Campaign {campaign_id} event: {list(event.keys())}")
            
            for node_name, node_state in event.items():
                # Map node to stage
                stage = stage_map.get(node_name, node_name)
                
                # Handle drafting nodes specially (all 4 run in parallel)
                if stage == "drafting":
                    if not current_drafting:
                        state_manager.update_stage(
                            campaign_id, "drafting", "running",
                            "Generating personalized drafts for all channels..."
                        )
                        current_drafting = True
                else:
                    current_drafting = False
                    state_manager.update_stage(
                        campaign_id, stage, "running",
                        f"Processing {stage}..."
                    )
                
                # Update full state
                state_manager.update_state(campaign_id, node_state)
                
                # Check if we need approval (interrupt point)
                if node_name == "approval" and node_state.get("drafts"):
                    state_manager.update_stage(
                        campaign_id, "approval", "waiting",
                        "Waiting for user approval..."
                    )
                    # Pause here - frontend will handle approval
                    return
                
                # Mark stage as completed
                if stage != "drafting" or (stage == "drafting" and "draft_instagram" in event):
                    state_manager.update_stage(
                        campaign_id, stage, "completed",
                        f"{stage.capitalize()} completed"
                    )
        
        # Final update
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            final_state = campaign["state"]
            if final_state.get("status") == "persisted":
                state_manager.update_stage(
                    campaign_id, "persistence", "completed",
                    "Campaign completed successfully"
                )
                campaign["status"] = "completed"
            
    except Exception as exc:
        logger.error(f"Campaign {campaign_id} failed: {exc}", exc_info=True)
        state_manager.update_stage(
            campaign_id, state_manager.get_campaign(campaign_id)["current_stage"],
            "failed", str(exc)
        )
        campaign = state_manager.get_campaign(campaign_id)
        if campaign:
            campaign["status"] = "failed"
            campaign["error"] = str(exc)
