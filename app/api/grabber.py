"""Grabber API endpoints for httpxCloud v1"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import structlog

from ..core.auth import get_current_user, require_admin
from ..core.models import GrabberStatus

logger = structlog.get_logger()

router = APIRouter()

# Global grabber state
grabber_state = GrabberStatus()
grabber_task: asyncio.Task = None


async def grabber_worker():
    """Simple grabber worker that generates domain permutations"""
    global grabber_state
    
    try:
        grabber_state.is_running = True
        grabber_state.started_at = datetime.now(timezone.utc)
        grabber_state.processed_count = 0
        grabber_state.generated_count = 0
        grabber_state.error_message = None
        
        logger.info("Grabber worker started")
        
        # Simulate domain grabbing process
        base_domains = ["example.com", "test.com", "demo.com"]
        prefixes = ["api", "admin", "dev", "staging", "www", "mail", "ftp"]
        suffixes = ["", "-old", "-new", "-backup", "-test"]
        
        total_combinations = len(base_domains) * len(prefixes) * len(suffixes)
        
        for domain in base_domains:
            for prefix in prefixes:
                for suffix in suffixes:
                    if not grabber_state.is_running:
                        logger.info("Grabber stopped by user")
                        return
                    
                    # Generate domain permutation
                    generated_domain = f"{prefix}{suffix}.{domain}"
                    
                    # Simulate processing time
                    await asyncio.sleep(0.1)
                    
                    grabber_state.processed_count += 1
                    grabber_state.generated_count += 1
                    
                    # Calculate ETA
                    if grabber_state.processed_count > 0:
                        progress = grabber_state.processed_count / total_combinations
                        elapsed = (datetime.now(timezone.utc) - grabber_state.started_at).total_seconds()
                        if progress > 0:
                            total_time = elapsed / progress
                            remaining_time = total_time - elapsed
                            grabber_state.estimated_completion = datetime.now(timezone.utc).replace(
                                microsecond=0
                            ) + datetime.timedelta(seconds=int(remaining_time))
        
        logger.info("Grabber worker completed", 
                   processed=grabber_state.processed_count,
                   generated=grabber_state.generated_count)
        
    except asyncio.CancelledError:
        logger.info("Grabber worker cancelled")
        grabber_state.error_message = "Worker cancelled"
        raise
    except Exception as e:
        logger.error("Grabber worker error", error=str(e))
        grabber_state.error_message = str(e)
    finally:
        grabber_state.is_running = False


@router.post("/grabber/start")
async def start_grabber(
    current_user = Depends(require_admin)
) -> Dict[str, Any]:
    """Start the domain grabber worker"""
    global grabber_task
    
    if grabber_state.is_running:
        raise HTTPException(status_code=400, detail="Grabber is already running")
    
    try:
        # Start the grabber task
        grabber_task = asyncio.create_task(grabber_worker())
        
        logger.info("Grabber started by admin", admin=current_user.get("username"))
        
        return {
            "message": "Grabber started successfully",
            "status": grabber_state.dict()
        }
        
    except Exception as e:
        logger.error("Failed to start grabber", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start grabber: {str(e)}")


@router.get("/grabber/status")
async def get_grabber_status(
    current_user = Depends(get_current_user)
) -> GrabberStatus:
    """Get current grabber status"""
    return grabber_state


@router.post("/grabber/stop")
async def stop_grabber(
    current_user = Depends(require_admin)
) -> Dict[str, str]:
    """Stop the domain grabber worker"""
    global grabber_task
    
    if not grabber_state.is_running:
        raise HTTPException(status_code=400, detail="Grabber is not running")
    
    try:
        # Cancel the grabber task
        if grabber_task and not grabber_task.done():
            grabber_task.cancel()
            try:
                await grabber_task
            except asyncio.CancelledError:
                pass
        
        grabber_state.is_running = False
        
        logger.info("Grabber stopped by admin", admin=current_user.get("username"))
        
        return {
            "message": "Grabber stopped successfully"
        }
        
    except Exception as e:
        logger.error("Failed to stop grabber", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to stop grabber: {str(e)}")