"""Results API endpoints for French panel UI"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from ..core.auth import get_current_user, require_admin
from ..core.models import Hit, ResultsFilterRequest, ProviderStatus
from ..core.scanner import scanner

router = APIRouter()

# In-memory storage for demonstration (replace with database in production)
hits_storage: Dict[str, Hit] = {}
provider_validators = {}  # Will store provider validation functions


@router.get("/results")
async def get_results(
    service: Optional[str] = Query(None, description="Filter by service type"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
    sort: str = Query("date_desc", regex="^(date_asc|date_desc)$", description="Sort order"),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get filtered and sorted results with counters"""
    
    # Get all hits
    all_hits = list(hits_storage.values())
    
    # Apply filters
    filtered_hits = all_hits
    if service and service != "all":
        filtered_hits = [h for h in filtered_hits if h.service == service]
    if validated is not None:
        filtered_hits = [h for h in filtered_hits if h.validated == validated]
    
    # Sort results
    reverse = sort == "date_desc"
    filtered_hits.sort(key=lambda h: h.discovered_at, reverse=reverse)
    
    # Calculate counters
    valides_count = len([h for h in all_hits if h.validated])
    invalides_count = len([h for h in all_hits if not h.validated])
    total_count = len(all_hits)
    
    return {
        "hits": [hit.model_dump() for hit in filtered_hits],
        "counters": {
            "valides": valides_count,
            "invalides": invalides_count, 
            "total": total_count
        },
        "filters": {
            "service": service,
            "validated": validated,
            "sort": sort
        }
    }


@router.get("/results/{hit_id}")
async def get_result_detail(
    hit_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Hit:
    """Get detailed result by ID"""
    
    if hit_id not in hits_storage:
        raise HTTPException(status_code=404, detail="Hit not found")
    
    return hits_storage[hit_id]


@router.post("/results/purge")
async def purge_results(
    current_user: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """Purge all results (admin only)"""
    
    global hits_storage
    count = len(hits_storage)
    hits_storage.clear()
    
    return {
        "message": f"Purged {count} results successfully",
        "status": "success"
    }


@router.post("/results/{hit_id}/validate")
async def validate_result(
    hit_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Validate a specific result using provider-specific checks"""
    
    if hit_id not in hits_storage:
        raise HTTPException(status_code=404, detail="Hit not found")
    
    hit = hits_storage[hit_id]
    
    # Perform safe validation based on service type
    validation_result = await _validate_provider_safe(hit.service, hit.provider_payload)
    
    # Update hit with validation results
    hit.validated = validation_result["status"] == ProviderStatus.VALID
    hit.provider_payload.update({
        "status": validation_result["status"],
        "reason": validation_result.get("reason", ""),
        "validated_at": datetime.now().isoformat()
    })
    
    return {
        "hit_id": hit_id,
        "validated": hit.validated,
        "validation_result": validation_result
    }


async def _validate_provider_safe(service: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe provider validation with strict timeouts and rate limiting"""
    
    # Mock validation for demonstration - in production this would make
    # safe, non-intrusive API calls with proper rate limiting
    
    validation_functions = {
        "aws": _validate_aws_safe,
        "sendgrid": _validate_sendgrid_safe,
        "mailgun": _validate_mailgun_safe,
        "twilio": _validate_twilio_safe,
        "brevo": _validate_brevo_safe,
        "sparkpost": _validate_sparkpost_safe
    }
    
    validator = validation_functions.get(service)
    if not validator:
        return {
            "status": ProviderStatus.UNKNOWN,
            "reason": f"No validator available for {service}"
        }
    
    try:
        return await validator(payload)
    except Exception as e:
        return {
            "status": ProviderStatus.UNKNOWN,
            "reason": f"Validation failed: {str(e)}"
        }


async def _validate_aws_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe AWS validation - check format only, no actual API calls"""
    api_key = payload.get("api_key", "")
    
    # Basic format validation
    if api_key.startswith("AKIA") and len(api_key) == 20:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid AWS access key format",
            "quota": "Unknown",
            "credits": "Unknown"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid AWS access key format"
    }


async def _validate_sendgrid_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe SendGrid validation"""
    api_key = payload.get("api_key", "")
    
    if api_key.startswith("SG.") and len(api_key) >= 69:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid SendGrid API key format"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid SendGrid API key format"
    }


async def _validate_mailgun_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe MailGun validation"""
    api_key = payload.get("api_key", "")
    
    if api_key.startswith("key-") and len(api_key) >= 36:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid MailGun API key format"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid MailGun API key format"
    }


async def _validate_twilio_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe Twilio validation"""
    api_key = payload.get("api_key", "")
    
    if api_key.startswith("AC") and len(api_key) == 34:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid Twilio Account SID format"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid Twilio Account SID format"
    }


async def _validate_brevo_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe Brevo validation"""
    api_key = payload.get("api_key", "")
    
    if api_key.startswith("xkeysib-") and len(api_key) >= 80:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid Brevo API key format"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid Brevo API key format"
    }


async def _validate_sparkpost_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safe SparkPost validation"""
    api_key = payload.get("api_key", "")
    
    # SparkPost API keys are typically 40 characters
    if len(api_key) >= 32:
        return {
            "status": ProviderStatus.VALID,
            "reason": "Valid SparkPost API key format"
        }
    
    return {
        "status": ProviderStatus.INVALID,
        "reason": "Invalid SparkPost API key format"
    }


# Helper function to add sample hits for testing
def add_sample_hit(service: str, url: str, api_key: str) -> str:
    """Add a sample hit for testing purposes"""
    
    hit_id = str(uuid.uuid4())
    host = url.split("://")[1].split("/")[0] if "://" in url else url.split("/")[0]
    path = "/" + "/".join(url.split("/")[3:]) if url.count("/") > 2 else "/"
    
    hit = Hit(
        id=hit_id,
        host=host,
        path=path,
        url=url,
        service=service,
        provider_payload={
            "api_key": api_key[:8] + "..." + api_key[-4:],  # Masked
            "status": ProviderStatus.UNKNOWN,
            "proxy_state": "active"
        },
        evidence_ref=f"evidence_{hit_id}"
    )
    
    hits_storage[hit_id] = hit
    return hit_id


# Initialize with sample data for testing
def init_sample_data():
    """Initialize with sample hits for demonstration"""
    
    sample_hits = [
        {
            "service": "aws",
            "url": "https://api.example.com/config",
            "api_key": "AKIA1234567890EXAMPLE"
        },
        {
            "service": "sendgrid", 
            "url": "https://app.test.com/mail-config.json",
            "api_key": "SG.abc123def456.ghi789jkl012mno345pqr678stu901vwx234yz"
        },
        {
            "service": "mailgun",
            "url": "https://dashboard.demo.org/api-keys",
            "api_key": "key-1234567890abcdef1234567890abcdef"
        },
        {
            "service": "twilio",
            "url": "https://www.sample.net/twilio.conf",
            "api_key": "AC1234567890abcdef1234567890abcdef12"
        },
        {
            "service": "brevo",
            "url": "https://mail.company.com/.env",
            "api_key": "xkeysib-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef-abcd1234"
        }
    ]
    
    for hit_data in sample_hits:
        add_sample_hit(hit_data["service"], hit_data["url"], hit_data["api_key"])

# Initialize sample data when module loads
init_sample_data()