from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Dict, Any
import json
import csv
import io
from datetime import datetime

from ..core.models import (
    ScanRequest, ScanResult, Finding, AuthRequest, 
    PasswordChangeRequest, ConfigModel
)
from ..core.auth import auth_manager, get_current_user, require_admin
from ..core.scanner import scanner
from ..core.config import config_manager

router = APIRouter()


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}


# Authentication endpoints
@router.post("/auth/login")
async def login(auth_request: AuthRequest):
    """Login endpoint"""
    user = auth_manager.authenticate_user(auth_request.username, auth_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    token = auth_manager.create_access_token(user.username, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "role": user.role
        },
        "first_run": auth_manager.is_first_run()
    }


@router.get("/auth/me")
async def auth_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current authenticated user payload"""
    return current_user


@router.post("/auth/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Change password endpoint"""
    success = auth_manager.change_password(
        current_user["sub"],
        request.old_password,
        request.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password"
        )
    
    return {"message": "Password changed successfully"}


# Configuration endpoints
@router.get("/config", dependencies=[Depends(require_admin)])
async def get_config() -> ConfigModel:
    """Get current configuration"""
    return config_manager.get_config()


@router.put("/config", dependencies=[Depends(require_admin)])
async def update_config(updates: Dict[str, Any]):
    """Update configuration"""
    config_manager.update_config(updates)
    return {"message": "Configuration updated successfully"}


# Scan lifecycle endpoints
@router.post("/scans", dependencies=[Depends(get_current_user)])
async def create_scan(scan_request: ScanRequest) -> Dict[str, str]:
    """Create and start a new scan"""
    scan_id = await scanner.start_scan(scan_request)
    return {"scan_id": scan_id, "status": "queued"}


@router.get("/scans", dependencies=[Depends(get_current_user)])
async def list_scans() -> List[ScanResult]:
    """List all scans"""
    return scanner.list_scans()


@router.get("/scans/{scan_id}", dependencies=[Depends(get_current_user)])
async def get_scan(scan_id: str) -> ScanResult:
    """Get scan details by ID"""
    scan_result = scanner.get_scan_result(scan_id)
    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan_result


@router.post("/scans/{scan_id}/stop", dependencies=[Depends(require_admin)])
async def stop_scan(scan_id: str):
    """Stop a running scan"""
    success = scanner.stop_scan(scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found or not running")
    return {"message": "Scan stopped successfully"}


# Results endpoints
@router.get("/scans/{scan_id}/findings", dependencies=[Depends(get_current_user)])
async def get_scan_findings(scan_id: str) -> List[Finding]:
    """Get findings for a scan"""
    findings = scanner.get_scan_findings(scan_id)
    return findings


@router.get("/scans/{scan_id}/export/json", dependencies=[Depends(get_current_user)])
async def export_findings_json(scan_id: str):
    """Export findings as JSON"""
    findings = scanner.get_scan_findings(scan_id)
    findings_data = [finding.model_dump() for finding in findings]
    
    json_str = json.dumps(findings_data, indent=2, default=str)
    
    return StreamingResponse(
        io.StringIO(json_str),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}_findings.json"}
    )


@router.get("/scans/{scan_id}/export/csv", dependencies=[Depends(get_current_user)])
async def export_findings_csv(scan_id: str):
    """Export findings as CSV"""
    findings = scanner.get_scan_findings(scan_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Provider', 'URL', 'First Seen', 'Last Seen', 'Evidence (Masked)'])
    
    # Write data
    for finding in findings:
        writer.writerow([
            finding.id,
            finding.provider,
            finding.url,
            finding.first_seen.isoformat(),
            finding.last_seen.isoformat(),
            finding.evidence_masked
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}_findings.csv"}
    )


@router.get("/scans/{scan_id}/evidence/{finding_id}", dependencies=[Depends(require_admin)])
async def get_finding_evidence(scan_id: str, finding_id: str):
    """Get full evidence for a finding (admin only)"""
    findings = scanner.get_scan_findings(scan_id)
    finding = next((f for f in findings if f.id == finding_id), None)
    
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    return {"evidence": finding.evidence}


# File upload endpoints
@router.post("/upload/targets", dependencies=[Depends(get_current_user)])
async def upload_targets_file(file: UploadFile = File(...)):
    """Upload targets file"""
    if not file.filename.endswith(('.txt', '.csv')):
        raise HTTPException(status_code=400, detail="Only .txt and .csv files are supported")
    
    content = await file.read()
    targets = []
    
    try:
        lines = content.decode('utf-8').strip().split('\n')
        targets = [line.strip() for line in lines if line.strip()]
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    return {"targets": targets, "count": len(targets)}


@router.post("/upload/wordlist", dependencies=[Depends(require_admin)])
async def upload_wordlist(file: UploadFile = File(...)):
    """Upload custom wordlist"""
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    
    content = await file.read()
    
    try:
        # Save to data directory
        wordlist_path = f"data/{file.filename}"
        with open(wordlist_path, 'wb') as f:
            f.write(content)
        
        # Count paths
        paths = content.decode('utf-8').strip().split('\n')
        path_count = len([line for line in paths if line.strip()])
        
        return {"filename": file.filename, "paths_count": path_count}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save wordlist: {str(e)}")


# Statistics endpoint
@router.get("/stats", dependencies=[Depends(get_current_user)])
async def get_statistics():
    """Get scan statistics"""
    scans = scanner.list_scans()
    
    total_scans = len(scans)
    running_scans = len([s for s in scans if s.status.value == "running"])
    completed_scans = len([s for s in scans if s.status.value == "completed"])
    failed_scans = len([s for s in scans if s.status.value == "failed"])
    
    total_findings = sum(len(scanner.get_scan_findings(s.id)) for s in scans)
    
    return {
        "total_scans": total_scans,
        "running_scans": running_scans,
        "completed_scans": completed_scans,
        "failed_scans": failed_scans,
        "total_findings": total_findings
    }