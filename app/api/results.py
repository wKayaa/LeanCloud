"""Results API endpoints for httpxCloud v1"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
import structlog

from ..core.auth import get_current_user, require_admin
from ..core.models import Hit, ProviderStatus
from ..core.database import get_db_session

logger = structlog.get_logger()

router = APIRouter()

# In-memory storage for demo - in production this would use a database
hits_storage: List[Hit] = []
hit_counters = {
    "total": 0,
    "validated": 0, 
    "invalid": 0,
    "aws": 0,
    "sendgrid": 0,
    "sparkpost": 0,
    "twilio": 0,
    "brevo": 0,
    "mailgun": 0
}


@router.get("/results")
async def list_results(
    service: Optional[str] = Query(None, description="Filter by service type"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
    sort: str = Query("date_desc", description="Sort order: date_asc, date_desc, service, status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=1000, description="Results per page"),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """List results with filtering and pagination"""
    
    try:
        # Filter results
        filtered_hits = hits_storage.copy()
        
        if service:
            filtered_hits = [h for h in filtered_hits if h.service == service]
            
        if validated is not None:
            filtered_hits = [h for h in filtered_hits if h.validated == validated]
        
        # Sort results
        if sort == "date_desc":
            filtered_hits.sort(key=lambda x: x.discovered_at, reverse=True)
        elif sort == "date_asc":
            filtered_hits.sort(key=lambda x: x.discovered_at)
        elif sort == "service":
            filtered_hits.sort(key=lambda x: x.service)
        elif sort == "status":
            filtered_hits.sort(key=lambda x: x.validated, reverse=True)
        
        # Paginate
        total_count = len(filtered_hits)
        paginated_hits = filtered_hits[offset:offset + limit]
        
        # Mask sensitive data for non-admin users
        if current_user.get("role") != "admin":
            for hit in paginated_hits:
                if hit.provider_payload and hit.provider_payload.masked_api_key:
                    # Further mask for viewers
                    hit.provider_payload.masked_api_key = "***HIDDEN***"
        
        return {
            "results": [hit.dict() for hit in paginated_hits],
            "pagination": {
                "total": total_count,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total_count
            },
            "counters": hit_counters
        }
        
    except Exception as e:
        logger.error("Failed to list results", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve results")


@router.get("/results/{hit_id}")
async def get_result_detail(
    hit_id: str,
    current_user = Depends(get_current_user)
) -> Hit:
    """Get detailed information for a specific hit"""
    
    # Find the hit
    hit = next((h for h in hits_storage if h.id == hit_id), None)
    if not hit:
        raise HTTPException(status_code=404, detail="Hit not found")
    
    # Mask data for non-admin users
    if current_user.get("role") != "admin":
        if hit.provider_payload and hit.provider_payload.masked_api_key:
            hit.provider_payload.masked_api_key = "***HIDDEN***"
    
    return hit


@router.post("/results/purge")
async def purge_all_results(
    current_user = Depends(require_admin)
) -> Dict[str, str]:
    """Admin-only: Purge all results"""
    
    try:
        global hits_storage, hit_counters
        
        purged_count = len(hits_storage)
        hits_storage.clear()
        
        # Reset counters
        hit_counters = {
            "total": 0,
            "validated": 0,
            "invalid": 0,
            "aws": 0,
            "sendgrid": 0, 
            "sparkpost": 0,
            "twilio": 0,
            "brevo": 0,
            "mailgun": 0
        }
        
        logger.info("Results purged by admin", count=purged_count, admin=current_user.get("username"))
        
        return {
            "message": f"Successfully purged {purged_count} results",
            "purged_count": purged_count
        }
        
    except Exception as e:
        logger.error("Failed to purge results", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to purge results")


@router.get("/results/counters")
async def get_result_counters(
    current_user = Depends(get_current_user)
) -> Dict[str, int]:
    """Get current result counters"""
    return hit_counters


def add_synthetic_hit(service: str, validated: bool = False) -> Hit:
    """Helper function to add synthetic hits for testing"""
    from ..core.models import ProviderPayload, ProviderStatus
    
    synthetic_keys = {
        "aws": "AKIA" + "X" * 16,
        "sendgrid": "SG." + "X" * 22 + "." + "X" * 43,
        "sparkpost": "sp_" + "X" * 32,
        "twilio": "AC" + "X" * 32,
        "brevo": "xkeysib-" + "X" * 64 + "-" + "X" * 16,
        "mailgun": "key-" + "X" * 32
    }
    
    hit = Hit(
        host=f"example-{service}.com",
        path="/.env",
        url=f"https://example-{service}.com/.env",
        service=service,
        validated=validated,
        provider_payload=ProviderPayload(
            masked_api_key=synthetic_keys.get(service, "XXX-MASKED-XXX"),
            status=ProviderStatus.VALID if validated else ProviderStatus.UNKNOWN,
            reason="Synthetic test data"
        ),
        evidence_ref=f"evidence_{service}_{datetime.now().timestamp()}"
    )
    
    hits_storage.append(hit)
    
    # Update counters
    hit_counters["total"] += 1
    if validated:
        hit_counters["validated"] += 1
    else:
        hit_counters["invalid"] += 1
    
    if service in hit_counters:
        hit_counters[service] += 1
    
    return hit


# Initialize with some synthetic data for demo
def init_synthetic_data():
    """Initialize with synthetic test data"""
    services = ["aws", "sendgrid", "sparkpost", "twilio", "brevo", "mailgun"]
    
    for service in services:
        # Add validated hits
        for i in range(2):
            add_synthetic_hit(service, validated=True)
        
        # Add unvalidated hits  
        for i in range(3):
            add_synthetic_hit(service, validated=False)


# Initialize on import
init_synthetic_data()