"""Security utilities for masking sensitive data and audit logging"""

import re
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()


def mask_secret(secret: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask sensitive data showing only first and last few characters
    
    Args:
        secret: The secret to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to show at start and end
        
    Returns:
        Masked string
    """
    if not secret or len(secret) <= visible_chars * 2:
        return mask_char * len(secret) if secret else ""
    
    start = secret[:visible_chars]
    end = secret[-visible_chars:]
    middle_length = len(secret) - (visible_chars * 2)
    
    return f"{start}{mask_char * middle_length}{end}"


def mask_email(email: str) -> str:
    """Mask email address preserving domain structure"""
    if not email or "@" not in email:
        return mask_secret(email)
    
    local, domain = email.rsplit("@", 1)
    masked_local = mask_secret(local, visible_chars=2)
    return f"{masked_local}@{domain}"


def mask_url(url: str) -> str:
    """Mask URL preserving structure but hiding sensitive parts"""
    # Pattern to match URLs with potential secrets
    patterns = [
        r"(api[_-]?key=)([^&\s]+)",
        r"(token=)([^&\s]+)",
        r"(password=)([^&\s]+)",
        r"(secret=)([^&\s]+)",
        r"(auth=)([^&\s]+)",
    ]
    
    masked_url = url
    for pattern in patterns:
        masked_url = re.sub(
            pattern, 
            lambda m: m.group(1) + mask_secret(m.group(2)), 
            masked_url, 
            flags=re.IGNORECASE
        )
    
    return masked_url


def mask_finding_evidence(evidence: str, service_type: str = "generic") -> str:
    """
    Mask finding evidence based on service type
    
    Args:
        evidence: Raw evidence string
        service_type: Type of service (aws, sendgrid, etc.)
        
    Returns:
        Masked evidence string
    """
    if not evidence:
        return evidence
    
    # Service-specific masking patterns
    if service_type.lower() == "aws":
        # AWS keys: AKIA... (20 chars), secret (40 chars)
        evidence = re.sub(r'AKIA[0-9A-Z]{16}', lambda m: mask_secret(m.group(), visible_chars=4), evidence)
        evidence = re.sub(r'[A-Za-z0-9/+=]{40}', lambda m: mask_secret(m.group(), visible_chars=4), evidence)
    
    elif service_type.lower() == "sendgrid":
        # SendGrid API keys: SG.xxx.xxx
        evidence = re.sub(r'SG\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', 
                         lambda m: f"SG.{mask_secret(m.group().split('.')[1])}.{mask_secret(m.group().split('.')[2])}", 
                         evidence)
    
    elif service_type.lower() == "stripe":
        # Stripe keys: sk_live_..., pk_live_...
        evidence = re.sub(r'[sp]k_(live|test)_[A-Za-z0-9]{24,}', 
                         lambda m: f"{m.group()[:8]}{mask_secret(m.group()[8:])}", 
                         evidence)
    
    # Generic patterns for any remaining secrets
    generic_patterns = [
        r'\b[A-Za-z0-9]{32,}\b',  # 32+ char alphanumeric strings
        r'\b[A-Za-z0-9+/]{40,}={0,2}\b',  # Base64-like strings
    ]
    
    for pattern in generic_patterns:
        evidence = re.sub(pattern, lambda m: mask_secret(m.group()), evidence)
    
    return evidence


def create_audit_log(
    action: str,
    user_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create audit log entry
    
    Args:
        action: Action performed (e.g., 'reveal_finding', 'export_data')
        user_id: User performing action
        scan_id: Related scan ID
        resource_type: Type of resource (finding, scan, etc.)
        resource_id: ID of the resource
        details: Additional details
        ip_address: Client IP address
        user_agent: Client user agent
        
    Returns:
        Audit log entry dictionary
    """
    return {
        "action": action,
        "user_id": user_id,
        "scan_id": scan_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "ip_address": ip_address,
        "user_agent": user_agent,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def log_audit_event(
    action: str,
    user_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """
    Log audit event to database
    
    This should be called for all sensitive operations like:
    - Revealing masked findings
    - Exporting data
    - Changing settings
    - Admin actions
    """
    try:
        from .database import get_db_session
        from .database import AuditLogDB
        import uuid
        
        audit_entry = AuditLogDB(
            id=uuid.uuid4(),
            user_id=user_id,
            scan_id=scan_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(timezone.utc)
        )
        
        async with get_db_session() as session:
            session.add(audit_entry)
            await session.commit()
            
        logger.info("Audit event logged", 
                   action=action, 
                   user_id=user_id, 
                   resource_type=resource_type)
                   
    except Exception as e:
        logger.error("Failed to log audit event", 
                    action=action, 
                    error=str(e))


class MaskingProfile:
    """Profile for different masking levels"""
    
    FULL = "full"  # Fully mask all sensitive data
    PARTIAL = "partial"  # Show some structure but mask secrets
    MINIMAL = "minimal"  # Minimal masking for admin users
    
    @classmethod
    def apply_profile(cls, data: Dict[str, Any], profile: str) -> Dict[str, Any]:
        """Apply masking profile to data"""
        if profile == cls.FULL:
            return cls._apply_full_masking(data)
        elif profile == cls.PARTIAL:
            return cls._apply_partial_masking(data)
        elif profile == cls.MINIMAL:
            return cls._apply_minimal_masking(data)
        else:
            return data
    
    @classmethod
    def _apply_full_masking(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply full masking"""
        masked_data = data.copy()
        
        # Mask common sensitive fields
        sensitive_fields = ['evidence', 'password', 'token', 'key', 'secret']
        for field in sensitive_fields:
            if field in masked_data:
                masked_data[field] = mask_secret(str(masked_data[field]))
        
        return masked_data
    
    @classmethod
    def _apply_partial_masking(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply partial masking"""
        masked_data = data.copy()
        
        # Use evidence_masked if available, otherwise mask evidence
        if 'evidence_masked' in data and data['evidence_masked']:
            masked_data['evidence'] = data['evidence_masked']
        elif 'evidence' in data:
            service_type = data.get('service', 'generic')
            masked_data['evidence'] = mask_finding_evidence(data['evidence'], service_type)
            
        return masked_data
    
    @classmethod
    def _apply_minimal_masking(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply minimal masking for admin users"""
        # For admin users, show more but still mask very sensitive parts
        return cls._apply_partial_masking(data)


# Export utility functions
def generate_export_filename(format_type: str, scan_id: str, timestamp: Optional[datetime] = None) -> str:
    """Generate standardized export filename"""
    if not timestamp:
        timestamp = datetime.now(timezone.utc)
    
    time_str = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"httpx_export_{scan_id}_{time_str}.{format_type}"


def sanitize_for_export(data: List[Dict[str, Any]], masking_profile: str = MaskingProfile.FULL) -> List[Dict[str, Any]]:
    """Sanitize data for export with appropriate masking"""
    sanitized = []
    
    for item in data:
        sanitized_item = MaskingProfile.apply_profile(item, masking_profile)
        
        # Remove internal fields that shouldn't be exported
        internal_fields = ['id', 'created_at', 'updated_at']
        for field in internal_fields:
            sanitized_item.pop(field, None)
        
        sanitized.append(sanitized_item)
    
    return sanitized