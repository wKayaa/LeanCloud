"""Scan API endpoints for httpxCloud v1 Phase 1"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import structlog

from ..core.models import ScanCreateRequest, ScanControlRequest, ScanResponse, ScanDB
from ..core.stats_manager import stats_manager
from ..core.masking import mask_evidence

logger = structlog.get_logger()

router = APIRouter(prefix="/scans", tags=["scans"])

# In-memory storage for Phase 1 (will be replaced with SQLite in later phases)
scans_storage: Dict[str, ScanDB] = {}


def generate_crack_id() -> str:
    """Generate a unique human-readable crack ID"""
    import random
    import string
    
    # Generate a random 8-character alphanumeric ID
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def _simulate_scan(scan_id: str, scan_data: ScanDB):
    """
    Simulate a scan for Phase 1 demonstration
    
    This will be replaced with real httpx/httpxCloud integration in Phase 2
    """
    logger.info("Starting scan simulation", scan_id=scan_id, crack_id=scan_data.crack_id)
    
    try:
        # Mark scan as started
        scan_data.status = "running"
        scan_data.started_at = datetime.now(timezone.utc)
        stats_manager.start_scan(scan_id)
        
        # Simulate processing URLs
        total_urls = scan_data.total_urls or 1000  # Default for simulation
        
        for i in range(total_urls):
            # Check if scan was stopped or paused
            current_scan = scans_storage.get(scan_id)
            if not current_scan or current_scan.status in ["stopped", "paused"]:
                logger.info("Scan simulation stopped", scan_id=scan_id, status=current_scan.status if current_scan else "deleted")
                return
            
            # Simulate processing delay
            await asyncio.sleep(0.1)  # 0.1 second per URL for demo
            
            # Update progress
            scan_data.processed_urls = i + 1
            stats_manager.update_scan_progress(scan_id, i + 1, total_urls)
            
            # Simulate finding hits (roughly 1 in 50 URLs)
            if i > 0 and i % 50 == 0:
                scan_data.hits += 1
                stats_manager.add_scan_hit(scan_id)
                logger.debug("Simulated hit found", scan_id=scan_id, hits=scan_data.hits)
            
            # Simulate occasional errors (roughly 1 in 200 URLs)
            if i > 0 and i % 200 == 0:
                scan_data.errors += 1
                stats_manager.add_scan_error(scan_id)
        
        # Mark scan as completed
        scan_data.status = "completed"
        scan_data.completed_at = datetime.now(timezone.utc)
        stats_manager.complete_scan(scan_id)
        
        logger.info("Scan simulation completed", 
                   scan_id=scan_id, 
                   processed=scan_data.processed_urls,
                   hits=scan_data.hits,
                   errors=scan_data.errors)
    
    except asyncio.CancelledError:
        logger.info("Scan simulation cancelled", scan_id=scan_id)
        scan_data.status = "stopped"
        stats_manager.stop_scan(scan_id)
    except Exception as e:
        logger.error("Scan simulation error", scan_id=scan_id, error=str(e))
        scan_data.status = "error"
        stats_manager.stop_scan(scan_id)


@router.post("/", response_model=ScanResponse)
async def create_scan(request: ScanCreateRequest) -> ScanResponse:
    """
    Create and start a new scan
    
    Phase 1: Creates scan with simulation, returns scan_id and crack_id
    """
    try:
        # Generate IDs
        scan_id = str(uuid.uuid4())
        crack_id = generate_crack_id()
        
        # Calculate estimated URLs based on modules/services selected
        estimated_urls = 100  # Base
        estimated_urls += len(request.modules) * 200  # Each module adds ~200 paths
        estimated_urls += len(request.services) * 50   # Each service adds ~50 checks
        
        if request.paths_content:
            # Count lines in uploaded paths
            estimated_urls += len([line for line in request.paths_content.split('\n') if line.strip()])
        
        # Create scan record
        scan_data = ScanDB(
            id=scan_id,
            crack_id=crack_id,
            name=request.name,
            status="queued",
            created_at=datetime.now(timezone.utc),
            timeout=request.timeout,
            list_id=request.list_id,
            modules=request.modules,
            services=request.services,
            concurrency=request.concurrency,
            total_urls=estimated_urls
        )
        
        # Store scan
        scans_storage[scan_id] = scan_data
        
        # Create stats tracking
        stats_manager.create_scan(scan_id, crack_id, estimated_urls)
        
        # Start scan simulation in background
        asyncio.create_task(_simulate_scan(scan_id, scan_data))
        
        logger.info("Scan created", 
                   scan_id=scan_id, 
                   crack_id=crack_id,
                   name=request.name,
                   modules=request.modules,
                   services=request.services,
                   estimated_urls=estimated_urls)
        
        return ScanResponse(scan_id=scan_id, crack_id=crack_id)
        
    except Exception as e:
        logger.error("Failed to create scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scan: {str(e)}"
        )


@router.post("/{scan_id}/control")
async def control_scan(scan_id: str, request: ScanControlRequest) -> Dict[str, str]:
    """
    Control scan execution (pause, resume, stop)
    """
    # Check if scan exists
    if scan_id not in scans_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    scan_data = scans_storage[scan_id]
    action = request.action
    
    try:
        if action == "pause":
            if scan_data.status == "running":
                scan_data.status = "paused"
                stats_manager.pause_scan(scan_id)
                logger.info("Scan paused", scan_id=scan_id, crack_id=scan_data.crack_id)
                return {"message": "Scan paused successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot pause scan in {scan_data.status} state"
                )
        
        elif action == "resume":
            if scan_data.status == "paused":
                scan_data.status = "running"
                stats_manager.resume_scan(scan_id)
                logger.info("Scan resumed", scan_id=scan_id, crack_id=scan_data.crack_id)
                return {"message": "Scan resumed successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot resume scan in {scan_data.status} state"
                )
        
        elif action == "stop":
            if scan_data.status in ["running", "paused", "queued"]:
                scan_data.status = "stopped"
                stats_manager.stop_scan(scan_id)
                logger.info("Scan stopped", scan_id=scan_id, crack_id=scan_data.crack_id)
                return {"message": "Scan stopped successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot stop scan in {scan_data.status} state"
                )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to control scan", scan_id=scan_id, action=action, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {action} scan: {str(e)}"
        )


@router.get("/{scan_id}")
async def get_scan(scan_id: str) -> Dict[str, Any]:
    """
    Get scan metadata and current status
    """
    if scan_id not in scans_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    scan_data = scans_storage[scan_id]
    stats = stats_manager.get_scan_stats(scan_id)
    
    response = {
        "id": scan_data.id,
        "crack_id": scan_data.crack_id,
        "name": scan_data.name,
        "status": scan_data.status,
        "created_at": scan_data.created_at.isoformat(),
        "started_at": scan_data.started_at.isoformat() if scan_data.started_at else None,
        "completed_at": scan_data.completed_at.isoformat() if scan_data.completed_at else None,
        "timeout": scan_data.timeout,
        "list_id": scan_data.list_id,
        "modules": scan_data.modules,
        "services": scan_data.services,
        "concurrency": scan_data.concurrency,
        "processed_urls": scan_data.processed_urls,
        "total_urls": scan_data.total_urls,
        "hits": scan_data.hits,
        "errors": scan_data.errors
    }
    
    # Add real-time stats if available
    if stats:
        response.update({
            "progress_percent": stats.progress_percent,
            "urls_per_sec": stats.urls_per_sec,
            "checks_per_sec": stats.checks_per_sec,
            "eta_seconds": stats.eta_seconds,
            "duration_seconds": stats.duration_seconds
        })
    
    return response


@router.get("/")
async def list_scans() -> Dict[str, Any]:
    """
    List all scans with pagination support
    """
    scans = []
    for scan_data in scans_storage.values():
        stats = stats_manager.get_scan_stats(scan_data.id)
        
        scan_info = {
            "id": scan_data.id,
            "crack_id": scan_data.crack_id,
            "name": scan_data.name,
            "status": scan_data.status,
            "created_at": scan_data.created_at.isoformat(),
            "processed_urls": scan_data.processed_urls,
            "total_urls": scan_data.total_urls,
            "hits": scan_data.hits,
            "errors": scan_data.errors,
        }
        
        if stats:
            scan_info.update({
                "progress_percent": stats.progress_percent,
                "urls_per_sec": stats.urls_per_sec,
                "eta_seconds": stats.eta_seconds
            })
        
        scans.append(scan_info)
    
    # Sort by creation time (newest first)
    scans.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "scans": scans,
        "total": len(scans),
        "page": 1,  # Simple pagination for Phase 1
        "per_page": len(scans)
    }