"""
app/api/state_manager.py
─────────────────────────
In-memory state management for single-user prototype.
Stores active campaigns and provides async event streaming.
"""

from __future__ import annotations
import asyncio
import uuid
from datetime import datetime
from typing import Any
import logging

logger = logging.getLogger(__name__)


class StateManager:
    """Manages campaign state and event broadcasting."""
    
    def __init__(self):
        self.campaigns: dict[str, dict[str, Any]] = {}
        self.event_queues: dict[str, list[asyncio.Queue]] = {}
    
    def create_campaign(self, input_data: dict[str, Any]) -> str:
        """Create a new campaign and return its ID."""
        campaign_id = str(uuid.uuid4())
        self.campaigns[campaign_id] = {
            "id": campaign_id,
            "status": "created",
            "current_stage": "pending",
            "input": input_data,
            "state": {},
            "created_at": datetime.utcnow(),
            "stages": {
                "ingestion": {"status": "pending", "message": ""},
                "persona": {"status": "pending", "message": ""},
                "drafting": {"status": "pending", "message": ""},
                "scoring": {"status": "pending", "message": ""},
                "approval": {"status": "pending", "message": ""},
                "execution": {"status": "pending", "message": ""},
                "persistence": {"status": "pending", "message": ""},
            }
        }
        self.event_queues[campaign_id] = []
        logger.info(f"Created campaign {campaign_id}")
        return campaign_id
    
    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        """Get campaign by ID."""
        return self.campaigns.get(campaign_id)
    
    def update_stage(self, campaign_id: str, stage: str, status: str, message: str = ""):
        """Update a specific stage status."""
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]["stages"][stage] = {
                "status": status,
                "message": message,
                "timestamp": datetime.utcnow()
            }
            self.campaigns[campaign_id]["current_stage"] = stage
            
            # Broadcast event
            event = {
                "type": "stage_update",
                "stage": stage,
                "status": status,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            asyncio.create_task(self._broadcast_event(campaign_id, event))
    
    def update_state(self, campaign_id: str, state: dict[str, Any]):
        """Update the full LangGraph state."""
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]["state"] = state
            self.campaigns[campaign_id]["status"] = state.get("status", "running")
    
    async def _broadcast_event(self, campaign_id: str, event: dict[str, Any]):
        """Broadcast event to all subscribers."""
        if campaign_id in self.event_queues:
            for queue in self.event_queues[campaign_id]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.error(f"Failed to broadcast event: {e}")
    
    def subscribe(self, campaign_id: str) -> asyncio.Queue:
        """Subscribe to campaign events."""
        queue = asyncio.Queue()
        if campaign_id not in self.event_queues:
            self.event_queues[campaign_id] = []
        self.event_queues[campaign_id].append(queue)
        return queue
    
    def unsubscribe(self, campaign_id: str, queue: asyncio.Queue):
        """Unsubscribe from campaign events."""
        if campaign_id in self.event_queues:
            try:
                self.event_queues[campaign_id].remove(queue)
            except ValueError:
                pass


# Global singleton for single-user prototype
state_manager = StateManager()
