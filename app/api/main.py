"""
app/api/main.py
───────────────
FastAPI application entry point.
"""

from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api.schemas import (
    CampaignStartRequest, CampaignResponse,
    DraftResponse, DraftActionRequest, StageUpdate
)
from app.api.state_manager import state_manager
from app.api.workflow_runner import run_campaign_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Outreach Engine API",
    version="1.0.0",
    description="LLM-powered hyper-personalized cold outreach automation"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite/React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory for files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "Outreach Engine API"}


@app.post("/api/v1/campaigns", response_model=CampaignResponse)
async def create_campaign(
    request: CampaignStartRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new outreach campaign.
    
    Accepts:
    - URL (LinkedIn, company website, etc.)
    - Plain text (profile description)
    - File path (PDF/DOC with mock data)
    """
    try:
        # Create campaign
        campaign_id = state_manager.create_campaign({
            "type": request.input_type,
            "content": request.content
        })
        
        # Start workflow in background
        background_tasks.add_task(
            run_campaign_workflow,
            campaign_id,
            request.content
        )
        
        campaign = state_manager.get_campaign(campaign_id)
        
        return CampaignResponse(
            campaign_id=campaign_id,
            status=campaign["status"],
            current_stage=campaign["current_stage"],
            drafts=[]
        )
        
    except Exception as exc:
        logger.error(f"Failed to create campaign: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/campaigns/upload")
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a PDF or DOC file and start a campaign.
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.pdf', '.docx', '.doc')):
            raise HTTPException(
                status_code=400,
                detail="Only PDF and DOC/DOCX files are supported"
            )
        
        # Save file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Uploaded file: {file_path}")
        
        # Create campaign with file path
        campaign_id = state_manager.create_campaign({
            "type": "file",
            "content": str(file_path)
        })
        
        # Start workflow in background
        background_tasks.add_task(
            run_campaign_workflow,
            campaign_id,
            str(file_path)
        )
        
        return CampaignResponse(
            campaign_id=campaign_id,
            status="created",
            current_stage="pending",
            drafts=[]
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"File upload failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str):
    """Get campaign status and results."""
    campaign = state_manager.get_campaign(campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Extract state data
    state = campaign.get("state", {})
    drafts_data = state.get("drafts", [])
    
    drafts = [
        DraftResponse(
            channel=d["channel"],
            subject=d.get("subject"),
            body=d["body"],
            score=d.get("score"),
            approved=d.get("approved", False)
        )
        for d in drafts_data
    ]
    
    return CampaignResponse(
        campaign_id=campaign_id,
        status=campaign["status"],
        current_stage=campaign["current_stage"],
        target_company=state.get("company"),
        target_role=state.get("role"),
        drafts=drafts,
        error=campaign.get("error")
    )


@app.get("/api/v1/campaigns/{campaign_id}/stream")
async def stream_campaign_updates(campaign_id: str):
    """
    Server-Sent Events endpoint for real-time campaign updates.
    """
    campaign = state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    async def event_generator():
        # Subscribe to campaign events
        queue = state_manager.subscribe(campaign_id)
        
        try:
            # Send current state first
            yield f"data: {campaign}\n\n"
            
            # Stream updates
            while True:
                event = await queue.get()
                yield f"data: {event}\n\n"
                
                # End stream if campaign completed or failed
                if event.get("type") == "stage_update":
                    if event.get("status") in ("completed", "failed"):
                        current_campaign = state_manager.get_campaign(campaign_id)
                        if current_campaign and current_campaign.get("status") in ("completed", "failed"):
                            break
        finally:
            state_manager.unsubscribe(campaign_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


class ApprovalRequest(BaseModel):
    """Request body for draft approvals."""
    approved: list[str] = []
    regen: list[str] = []
    skipped: list[str] = []


@app.post("/api/v1/campaigns/{campaign_id}/approve")
async def approve_drafts(
    campaign_id: str,
    request: ApprovalRequest
):
    """
    Handle draft approval/regeneration.
    User selects which channels to approve or regenerate.
    """
    campaign = state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Update state with user choices
    state = campaign.get("state", {})
    state["approved_channels"] = request.approved
    state["regen_channels"] = request.regen
    state["__resume__"] = {"approved": request.approved, "regen": request.regen}
    
    state_manager.update_state(campaign_id, state)
    
    # TODO: Resume workflow from approval node
    # For prototype, we'll handle this manually
    
    return {"status": "ok", "approved": request.approved, "regen": request.regen}


# ═══════════════════════════════════════════════════════════════════════════
# STATIC FILES (for serving frontend in production)
# ═══════════════════════════════════════════════════════════════════════════

# Uncomment when frontend is built
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
