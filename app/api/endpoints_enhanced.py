"""Enhanced API endpoints for httpxCloud v1"""

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import structlog

from ..core.auth import get_current_user, require_admin
from ..core.database import get_db_session, ScanDB, FindingDB, EventDB, AuditLogDB, ListDB
from ..core.redis_manager import get_redis
from ..core.scanner_enhanced import enhanced_scanner
from ..core.httpx_executor import httpx_executor
from ..core.notifications import notification_manager
from ..core.metrics import metrics
from ..core.config import config_manager
from ..core.models import (
    ScanRequest, ScanResult, ScanControlRequest, Finding, 
    HitExportRequest, NotificationConfig, UserPreferences,
    WSEventType
)

# Import new API routers
from .results import router as results_router
from .grabber import router as grabber_router
from .settings import router as settings_router

logger = structlog.get_logger()

router = APIRouter()

# Include new API routers
router.include_router(results_router, prefix="", tags=["results"])
router.include_router(grabber_router, prefix="", tags=["grabber"])
router.include_router(settings_router, prefix="", tags=["settings"])

# Authentication endpoints
@router.get("/auth/me")
async def auth_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current authenticated user payload"""
    from ..core.auth import auth_manager
    return {
        **current_user,
        "first_run": auth_manager.is_first_run()
    }


@router.post("/auth/change-password")
async def change_password(
    request: Dict[str, str],
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """Change user password"""
    from ..core.auth import auth_manager
    
    # Extract passwords from request body
    old_password = request.get("old_password")
    new_password = request.get("new_password")
    
    if not old_password or not new_password:
        raise HTTPException(
            status_code=400, 
            detail="Both old_password and new_password are required"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    # Change password
    success = auth_manager.change_password(
        current_user["sub"], 
        old_password, 
        new_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    return {"message": "Password changed successfully"}

# Health and metrics endpoints
@router.get("/healthz")
@router.get("/readyz")
async def health_check():
    """Health check endpoint with service status"""
    from ..core.redis_manager import get_redis
    from ..core.database import async_engine
    
    status = {
        "status": "healthy",
        "service": "httpx_scanner",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        if async_engine:
            async with async_engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            status["components"]["database"] = "healthy"
        else:
            status["components"]["database"] = "not_initialized"
    except Exception as e:
        status["components"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "degraded"
    
    # Check Redis
    try:
        redis_manager = get_redis()
        if await redis_manager.is_healthy():
            status["components"]["redis"] = "healthy"
        else:
            status["components"]["redis"] = "unhealthy"
            status["status"] = "degraded"
    except Exception:
        status["components"]["redis"] = "not_initialized"
        status["status"] = "degraded"
    
    return status

@router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    metrics_data = metrics.get_metrics()
    return StreamingResponse(
        io.StringIO(metrics_data),
        media_type=metrics.get_content_type()
    )

# Enhanced scan endpoints
@router.post("/scans", dependencies=[Depends(get_current_user)])
async def create_scan(scan_request: ScanRequest) -> Dict[str, str]:
    """Create and start a new scan with enhanced features"""
    try:
        # Validate request
        if not scan_request.targets:
            raise HTTPException(status_code=400, detail="No targets provided")
        
        if scan_request.concurrency > 50000:
            raise HTTPException(status_code=400, detail="Concurrency exceeds maximum limit of 50,000")
        
        # Start scan
        scan_id = await enhanced_scanner.start_scan(scan_request)
        
        # Update metrics
        metrics.scan_started(
            scan_id, 
            len(scan_request.targets), 
            0,  # URLs will be counted later
            scan_request.concurrency
        )
        
        logger.info("Scan created via API", scan_id=scan_id, 
                   targets=len(scan_request.targets))
        
        return {
            "scan_id": scan_id,
            "crack_id": enhanced_scanner.get_scan_result(scan_id).crack_id,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error("Failed to create scan", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scans", dependencies=[Depends(get_current_user)])
async def list_scans(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """List scans with pagination and filtering"""
    try:
        # Build query
        query = select(ScanDB).order_by(ScanDB.created_at.desc())
        
        if status:
            query = query.where(ScanDB.status == status)
        
        # Get total count
        count_query = select(func.count(ScanDB.id))
        if status:
            count_query = count_query.where(ScanDB.status == status)
        
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        scan_records = result.scalars().all()
        
        # Convert to response format
        scans = []
        for scan_record in scan_records:
            # Get live data if scan is active
            scan_result = enhanced_scanner.get_scan_result(str(scan_record.id))
            if scan_result:
                # Use live data
                scan_data = scan_result.model_dump()
            else:
                # Use database data
                scan_data = {
                    "id": str(scan_record.id),
                    "crack_id": scan_record.crack_id,
                    "status": scan_record.status,
                    "created_at": scan_record.created_at.isoformat(),
                    "started_at": scan_record.started_at.isoformat() if scan_record.started_at else None,
                    "completed_at": scan_record.completed_at.isoformat() if scan_record.completed_at else None,
                    "targets": scan_record.targets,
                    "total_urls": scan_record.total_urls,
                    "processed_urls": scan_record.processed_urls,
                    "findings_count": scan_record.findings_count,
                    "hits_count": scan_record.hits_count,
                    "progress_percent": scan_record.progress_percent,
                    "checks_per_sec": scan_record.checks_per_sec,
                    "urls_per_sec": scan_record.urls_per_sec,
                    "error_message": scan_record.error_message
                }
            
            scans.append(scan_data)
        
        return {
            "scans": scans,
            "pagination": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error("Failed to list scans", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scans/{scan_id}", dependencies=[Depends(get_current_user)])
async def get_scan(scan_id: str, session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """Get detailed scan information"""
    try:
        # Try to get live data first
        scan_result = enhanced_scanner.get_scan_result(scan_id)
        if scan_result:
            return scan_result.model_dump()
        
        # Fall back to database
        result = await session.execute(
            select(ScanDB).where(ScanDB.id == scan_id)
        )
        scan_record = result.scalar_one_or_none()
        
        if not scan_record:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return {
            "id": str(scan_record.id),
            "crack_id": scan_record.crack_id,
            "status": scan_record.status,
            "created_at": scan_record.created_at.isoformat(),
            "started_at": scan_record.started_at.isoformat() if scan_record.started_at else None,
            "completed_at": scan_record.completed_at.isoformat() if scan_record.completed_at else None,
            "targets": scan_record.targets,
            "total_urls": scan_record.total_urls,
            "processed_urls": scan_record.processed_urls,
            "findings_count": scan_record.findings_count,
            "hits_count": scan_record.hits_count,
            "progress_percent": scan_record.progress_percent,
            "checks_per_sec": scan_record.checks_per_sec,
            "urls_per_sec": scan_record.urls_per_sec,
            "error_message": scan_record.error_message,
            "config": {
                "targets": scan_record.targets,
                "wordlist": scan_record.wordlist,
                "modules": scan_record.modules,
                "concurrency": scan_record.concurrency,
                "rate_limit": scan_record.rate_limit,
                "timeout": scan_record.timeout,
                "follow_redirects": scan_record.follow_redirects,
                "regex_rules": scan_record.regex_rules,
                "path_rules": scan_record.path_rules,
                "notes": scan_record.notes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scan", scan_id=scan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scans/{scan_id}/control", dependencies=[Depends(get_current_user)])
async def control_scan(scan_id: str, control_request: ScanControlRequest) -> Dict[str, str]:
    """Control scan execution (start, pause, resume, stop)"""
    try:
        action = control_request.action
        
        if action == "pause":
            success = await enhanced_scanner.pause_scan(scan_id)
        elif action == "resume":
            success = await enhanced_scanner.resume_scan(scan_id)
        elif action == "stop":
            success = await enhanced_scanner.stop_scan(scan_id)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
        if not success:
            raise HTTPException(status_code=404, detail="Scan not found or action not applicable")
        
        logger.info("Scan control action executed", scan_id=scan_id, action=action)
        
        return {"message": f"Scan {action} executed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to control scan", scan_id=scan_id, action=control_request.action, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# New endpoints for live scan data
@router.get("/scans/{scan_id}/logs", dependencies=[Depends(get_current_user)])
async def get_scan_logs(
    scan_id: str,
    tail: int = Query(500, ge=1, le=5000, description="Number of recent log lines to return")
) -> Dict[str, Any]:
    """Get recent logs for a scan"""
    try:
        # For now, return basic info - logs would come from WebSocket in real implementation
        # This endpoint provides fallback access when WebSocket isn't available
        scan_result = enhanced_scanner.get_scan_result(scan_id)
        if not scan_result:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get httpx executor stats if available
        stats = httpx_executor.get_scan_stats(scan_id)
        
        logs = []
        if scan_result.status == ScanStatus.RUNNING:
            logs.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "message": f"Scan is running - processed {scan_result.processed_urls} URLs"
            })
            
            if stats:
                logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "info", 
                    "message": f"Performance: {stats.get('processed_urls', 0)} URLs processed, "
                              f"{stats.get('hits', 0)} hits, {stats.get('errors', 0)} errors"
                })
        elif scan_result.status == ScanStatus.COMPLETED:
            logs.append({
                "timestamp": scan_result.completed_at.isoformat() if scan_result.completed_at else datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "message": f"Scan completed - {scan_result.findings_count} findings"
            })
        elif scan_result.status == ScanStatus.FAILED:
            logs.append({
                "timestamp": scan_result.completed_at.isoformat() if scan_result.completed_at else datetime.now(timezone.utc).isoformat(),
                "level": "error",
                "message": f"Scan failed: {scan_result.error_message or 'Unknown error'}"
            })
        
        return {
            "scan_id": scan_id,
            "logs": logs[-tail:],  # Return last N entries
            "total_logs": len(logs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scan logs", scan_id=scan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scans/{scan_id}/progress", dependencies=[Depends(get_current_user)])
async def get_scan_progress(scan_id: str) -> Dict[str, Any]:
    """Get detailed progress information for a scan"""
    try:
        # Validate scan_id as UUID
        try:
            import uuid
            uuid.UUID(scan_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scan ID format")
        
        scan_result = enhanced_scanner.get_scan_result(scan_id)
        if not scan_result:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get executor stats for additional detail
        stats = httpx_executor.get_scan_stats(scan_id)
        
        progress_data = {
            "scan_id": scan_id,
            "status": scan_result.status.value,
            "processed_urls": scan_result.processed_urls,
            "total_urls": scan_result.total_urls,
            "progress_percent": scan_result.progress_percent,
            "findings_count": scan_result.findings_count,
            "hits_count": scan_result.hits_count,
            "checks_per_sec": scan_result.checks_per_sec,
            "urls_per_sec": scan_result.urls_per_sec,
            "eta_seconds": scan_result.eta_seconds,
            "started_at": scan_result.started_at.isoformat() if scan_result.started_at else None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Add executor-specific stats if available
        if stats:
            progress_data.update({
                "executor_stats": {
                    "processed_urls": stats.get('processed_urls', 0),
                    "hits": stats.get('hits', 0),
                    "errors": stats.get('errors', 0),
                    "start_time": stats.get('start_time', 0),
                    "last_update": stats.get('last_update', 0)
                }
            })
        
        return progress_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scan progress", scan_id=scan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Enhanced findings/hits endpoints
@router.get("/scans/{scan_id}/hits", dependencies=[Depends(get_current_user)])
async def get_scan_hits(
    scan_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: Optional[str] = Query(None),
    works: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get scan hits/findings with filtering"""
    try:
        # Build query
        query = select(FindingDB).where(FindingDB.scan_id == scan_id).order_by(FindingDB.created_at.desc())
        
        # Apply filters
        if service:
            query = query.where(FindingDB.service == service)
        if works is not None:
            query = query.where(FindingDB.works == works)
        if severity:
            query = query.where(FindingDB.severity == severity)
        
        # Get total count
        count_query = select(func.count(FindingDB.id)).where(FindingDB.scan_id == scan_id)
        if service:
            count_query = count_query.where(FindingDB.service == service)
        if works is not None:
            count_query = count_query.where(FindingDB.works == works)
        if severity:
            count_query = count_query.where(FindingDB.severity == severity)
        
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        finding_records = result.scalars().all()
        
        # Convert to response format
        hits = []
        for finding in finding_records:
            hit_data = {
                "id": str(finding.id),
                "scan_id": str(finding.scan_id),
                "crack_id": finding.crack_id,
                "service": finding.service,
                "pattern_id": finding.pattern_id,
                "url": finding.url,
                "source_url": finding.source_url,
                "evidence_masked": finding.evidence_masked,  # Always masked by default
                "works": finding.works,
                "confidence": finding.confidence,
                "severity": finding.severity,
                "regions": finding.regions,
                "capabilities": finding.capabilities,
                "quotas": finding.quotas,
                "verified_identities": finding.verified_identities,
                "created_at": finding.created_at.isoformat()
            }
            hits.append(hit_data)
        
        return {
            "hits": hits,
            "pagination": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error("Failed to get scan hits", scan_id=scan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hits/{hit_id}/reveal", dependencies=[Depends(get_current_user)])
async def reveal_hit(
    hit_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Reveal unmasked evidence for a hit (with audit logging)"""
    try:
        # Get finding
        result = await session.execute(
            select(FindingDB).where(FindingDB.id == hit_id)
        )
        finding = result.scalar_one_or_none()
        
        if not finding:
            raise HTTPException(status_code=404, detail="Hit not found")
        
        # Log audit event
        audit_log = AuditLogDB(
            user_id=current_user.get("sub"),
            scan_id=finding.scan_id,
            action="reveal_hit",
            resource_type="finding",
            resource_id=hit_id,
            details={"service": finding.service, "severity": finding.severity}
        )
        session.add(audit_log)
        await session.commit()
        
        logger.info("Hit evidence revealed", hit_id=hit_id, user_id=current_user.get("sub"))
        
        return {
            "id": str(finding.id),
            "evidence": finding.evidence,  # Unmasked evidence
            "evidence_masked": finding.evidence_masked,
            "revealed_at": datetime.now(timezone.utc).isoformat(),
            "revealed_by": current_user.get("sub")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reveal hit", hit_id=hit_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scans/{scan_id}/export", dependencies=[Depends(get_current_user)])
async def export_hits(
    scan_id: str,
    export_request: HitExportRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Export hits in CSV or JSONL format"""
    try:
        # Build query
        query = select(FindingDB).where(FindingDB.scan_id == scan_id).order_by(FindingDB.created_at.desc())
        
        # Apply filters
        if export_request.service_filter:
            query = query.where(FindingDB.service == export_request.service_filter)
        if export_request.works_filter is not None:
            query = query.where(FindingDB.works == export_request.works_filter)
        if export_request.date_from:
            query = query.where(FindingDB.created_at >= export_request.date_from)
        if export_request.date_to:
            query = query.where(FindingDB.created_at <= export_request.date_to)
        
        result = await session.execute(query)
        findings = result.scalars().all()
        
        # Log audit event if revealing evidence
        if export_request.reveal:
            audit_log = AuditLogDB(
                user_id=current_user.get("sub"),
                scan_id=scan_id,
                action="export_hits_revealed",
                resource_type="scan",
                resource_id=scan_id,
                details={"format": export_request.format, "count": len(findings)}
            )
            session.add(audit_log)
            await session.commit()
        
        # Generate export data
        if export_request.format == "csv":
            return _generate_csv_export(findings, export_request.reveal)
        else:  # jsonl
            return _generate_jsonl_export(findings, export_request.reveal)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export hits", scan_id=scan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

def _generate_csv_export(findings, reveal: bool):
    """Generate CSV export"""
    output = io.StringIO()
    
    fieldnames = [
        "id", "scan_id", "crack_id", "service", "pattern_id", "url", "source_url",
        "evidence", "works", "confidence", "severity", "regions", "capabilities",
        "verified_identities", "created_at"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for finding in findings:
        row = {
            "id": str(finding.id),
            "scan_id": str(finding.scan_id),
            "crack_id": finding.crack_id,
            "service": finding.service,
            "pattern_id": finding.pattern_id,
            "url": finding.url,
            "source_url": finding.source_url,
            "evidence": finding.evidence if reveal else finding.evidence_masked,
            "works": finding.works,
            "confidence": finding.confidence,
            "severity": finding.severity,
            "regions": ",".join(finding.regions) if finding.regions else "",
            "capabilities": ",".join(finding.capabilities) if finding.capabilities else "",
            "verified_identities": ",".join(finding.verified_identities) if finding.verified_identities else "",
            "created_at": finding.created_at.isoformat()
        }
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hits_export.csv"}
    )

def _generate_jsonl_export(findings, reveal: bool):
    """Generate JSONL export"""
    def generate():
        for finding in findings:
            data = {
                "id": str(finding.id),
                "scan_id": str(finding.scan_id),
                "crack_id": finding.crack_id,
                "service": finding.service,
                "pattern_id": finding.pattern_id,
                "url": finding.url,
                "source_url": finding.source_url,
                "evidence": finding.evidence if reveal else finding.evidence_masked,
                "works": finding.works,
                "confidence": finding.confidence,
                "severity": finding.severity,
                "regions": finding.regions,
                "capabilities": finding.capabilities,
                "quotas": finding.quotas,
                "verified_identities": finding.verified_identities,
                "created_at": finding.created_at.isoformat()
            }
            yield json.dumps(data) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=hits_export.jsonl"}
    )

# File upload endpoints
@router.post("/upload/wordlist", dependencies=[Depends(get_current_user)])
async def upload_wordlist(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Upload a wordlist file"""
    try:
        if not file.filename.endswith(('.txt', '.list')):
            raise HTTPException(status_code=400, detail="Only .txt and .list files are supported")
        
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Count paths
        paths = [line.strip() for line in content_str.split('\n') if line.strip()]
        paths_count = len(paths)
        
        if paths_count == 0:
            raise HTTPException(status_code=400, detail="Wordlist is empty")
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        
        # Save to filesystem
        wordlists_dir = Path("data/wordlists")
        wordlists_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = wordlists_dir / safe_filename
        with open(file_path, 'w') as f:
            f.write(content_str)
        
        # Save to database
        wordlist_record = ListDB(
            name=file.filename or safe_filename,
            filename=safe_filename,
            list_type="wordlist",
            size=paths_count,
            file_size=len(content),
            description=f"Uploaded wordlist with {paths_count} paths"
        )
        session.add(wordlist_record)
        await session.commit()
        
        logger.info("Wordlist uploaded", filename=safe_filename, paths_count=paths_count)
        
        return {
            "filename": safe_filename,
            "original_filename": file.filename,
            "paths_count": paths_count,
            "file_size": len(content),
            "uploaded_at": wordlist_record.uploaded_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload wordlist", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wordlists", dependencies=[Depends(get_current_user)])
async def list_wordlists(session: AsyncSession = Depends(get_db_session)) -> List[Dict[str, Any]]:
    """List uploaded wordlists"""
    try:
        result = await session.execute(
            select(ListDB).where(ListDB.list_type == "wordlist").order_by(ListDB.created_at.desc())
        )
        wordlists = result.scalars().all()
        
        return [
            {
                "id": str(wordlist.id),
                "filename": wordlist.filename,
                "name": wordlist.name,
                "size": wordlist.size,
                "file_size": wordlist.file_size,
                "created_at": wordlist.created_at.isoformat()
            }
            for wordlist in wordlists
        ]
        
    except Exception as e:
        logger.error("Failed to list wordlists", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Notification testing endpoints
@router.post("/test-notification", dependencies=[Depends(require_admin)])
async def test_notification(
    channel: str = Query(..., pattern="^(telegram|slack|discord|webhook)$"),
    config_override: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Test notification configuration"""
    try:
        if channel == "telegram":
            config = config_manager.get_config()
            bot_token = config_override.get("bot_token") if config_override else config.telegram_bot_token
            chat_id = config_override.get("chat_id") if config_override else config.telegram_chat_id
            
            if not bot_token or not chat_id:
                raise HTTPException(status_code=400, detail="Telegram bot token and chat ID required")
            
            success = await notification_manager.test_telegram(bot_token, chat_id)
            
        elif channel == "slack":
            config = config_manager.get_config()
            webhook_url = config_override.get("webhook_url") if config_override else config.slack_webhook_url
            
            if not webhook_url:
                raise HTTPException(status_code=400, detail="Slack webhook URL required")
            
            success = await notification_manager.test_slack(webhook_url)
            
        elif channel == "discord":
            config = config_manager.get_config()
            webhook_url = config_override.get("webhook_url") if config_override else config.discord_webhook_url
            
            if not webhook_url:
                raise HTTPException(status_code=400, detail="Discord webhook URL required")
            
            success = await notification_manager.test_discord(webhook_url)
            
        elif channel == "webhook":
            webhook_url = config_override.get("webhook_url") if config_override else None
            secret = config_override.get("secret") if config_override else None
            
            if not webhook_url:
                raise HTTPException(status_code=400, detail="Webhook URL required")
            
            success = await notification_manager.test_webhook(webhook_url, secret)
        
        return {"success": success, "message": f"{channel.title()} test completed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test notification", channel=channel, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Statistics and dashboard endpoints
@router.get("/stats/dashboard", dependencies=[Depends(get_current_user)])
async def get_dashboard_stats(session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """Get dashboard statistics"""
    try:
        # Active scans
        active_scans_count = len(enhanced_scanner.active_scans)
        
        # Database stats
        total_scans_result = await session.execute(select(func.count(ScanDB.id)))
        total_scans = total_scans_result.scalar()
        
        completed_scans_result = await session.execute(
            select(func.count(ScanDB.id)).where(ScanDB.status == "completed")
        )
        completed_scans = completed_scans_result.scalar()
        
        total_hits_result = await session.execute(select(func.count(FindingDB.id)))
        total_hits = total_hits_result.scalar()
        
        verified_hits_result = await session.execute(
            select(func.count(FindingDB.id)).where(FindingDB.works == True)
        )
        verified_hits = verified_hits_result.scalar()
        
        # Service breakdown
        service_stats_result = await session.execute(
            select(FindingDB.service, func.count(FindingDB.id))
            .group_by(FindingDB.service)
            .order_by(func.count(FindingDB.id).desc())
        )
        service_stats = {service: count for service, count in service_stats_result.fetchall()}
        
        return {
            "active_scans": active_scans_count,
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "total_hits": total_hits,
            "verified_hits": verified_hits,
            "service_breakdown": service_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get dashboard stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Configuration endpoints
@router.get("/settings", dependencies=[Depends(get_current_user)])
async def get_settings() -> Dict[str, Any]:
    """Get current settings"""
    try:
        config = config_manager.get_config()
        
        # Return safe config (no secrets)
        return {
            "auth_required": config.auth_required,
            "rate_limit_per_minute": config.rate_limit_per_minute,
            "max_scan_retention_days": config.max_scan_retention_days,
            "max_concurrency": config.max_concurrency,
            "adaptive_concurrency": config.adaptive_concurrency,
            "enable_backpressure": config.enable_backpressure,
            "queue_max_size": config.queue_max_size,
            "batch_size": config.batch_size,
            "notifications": {
                "telegram_enabled": bool(config.telegram_bot_token and config.telegram_chat_id),
                "slack_enabled": bool(config.slack_webhook_url),
                "discord_enabled": bool(config.discord_webhook_url),
                "webhook_enabled": bool(config.webhook_secret)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/settings", dependencies=[Depends(require_admin)])
async def update_settings(updates: Dict[str, Any]) -> Dict[str, str]:
    """Update settings"""
    try:
        success = config_manager.update_config(updates)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update configuration")
        
        logger.info("Settings updated", updates=list(updates.keys()))
        
        return {"message": "Settings updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))