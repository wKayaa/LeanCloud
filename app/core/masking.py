"""Masking utilities for sensitive data in httpxCloud v1"""

import re
from typing import Any, Dict, List, Optional, Union


def mask_secret(value: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask sensitive strings while keeping some characters visible for identification
    
    Args:
        value: The string to mask
        mask_char: Character to use for masking (default: "*")  
        visible_chars: Number of characters to keep visible at start/end
    
    Returns:
        Masked string with pattern: visible_chars + masked_middle + visible_chars
    """
    if not value or len(value) <= visible_chars * 2:
        return mask_char * len(value) if value else ""
    
    start = value[:visible_chars]
    end = value[-visible_chars:] if visible_chars > 0 else ""
    middle_length = len(value) - (visible_chars * 2)
    
    return f"{start}{mask_char * middle_length}{end}"


def mask_url(url: str) -> str:
    """
    Mask sensitive parts of URLs (credentials, sensitive paths)
    
    Args:
        url: URL to mask
        
    Returns:
        URL with sensitive parts masked
    """
    if not url:
        return ""
    
    # Mask credentials in URL
    url_pattern = r"(https?://)([^:/@]+):([^@]+)@(.+)"
    match = re.match(url_pattern, url)
    if match:
        protocol, username, password, rest = match.groups()
        masked_username = mask_secret(username, visible_chars=2)
        masked_password = mask_secret(password, visible_chars=0)  # Fully mask passwords
        return f"{protocol}{masked_username}:{masked_password}@{rest}"
    
    # Mask potential sensitive query parameters
    sensitive_params = ['key', 'token', 'secret', 'password', 'pwd', 'auth', 'api_key', 'apikey']
    for param in sensitive_params:
        pattern = rf"([?&]{param}=)([^&]+)"
        url = re.sub(pattern, lambda m: m.group(1) + mask_secret(m.group(2), visible_chars=2), url, flags=re.IGNORECASE)
    
    return url


def mask_json_values(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Recursively mask sensitive values in JSON/dict data
    
    Args:
        data: Dictionary to process
        sensitive_keys: List of keys to mask (case-insensitive)
        
    Returns:
        Dictionary with sensitive values masked
    """
    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'secret', 'token', 'key', 'auth', 'credential', 
            'pwd', 'pass', 'api_key', 'apikey', 'access_key', 'private_key',
            'bot_token', 'webhook_secret', 'chat_id'
        ]
    
    sensitive_keys_lower = [k.lower() for k in sensitive_keys]
    
    def mask_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key.lower() in sensitive_keys_lower and isinstance(value, str):
                    result[key] = mask_secret(value, visible_chars=3)
                elif isinstance(value, (dict, list)):
                    result[key] = mask_recursive(value)
                else:
                    result[key] = value
            return result
        elif isinstance(obj, list):
            return [mask_recursive(item) for item in obj]
        else:
            return obj
    
    return mask_recursive(data)


def mask_evidence(evidence: str, evidence_type: str = "generic") -> str:
    """
    Mask evidence based on its type for display purposes
    
    Args:
        evidence: The evidence string to mask
        evidence_type: Type of evidence (aws_key, email, url, etc.)
        
    Returns:
        Appropriately masked evidence
    """
    if not evidence:
        return ""
    
    # Different masking strategies based on evidence type
    if evidence_type == "aws_key":
        # AWS keys: show prefix + 4 chars at end
        if evidence.startswith("AKIA"):
            return f"AKIA{mask_secret(evidence[4:], visible_chars=2)}"
        return mask_secret(evidence, visible_chars=4)
    
    elif evidence_type == "email":
        # Email: mask username but keep domain visible
        if "@" in evidence:
            username, domain = evidence.rsplit("@", 1)
            masked_username = mask_secret(username, visible_chars=2)
            return f"{masked_username}@{domain}"
        return mask_secret(evidence, visible_chars=3)
    
    elif evidence_type == "url":
        return mask_url(evidence)
    
    elif evidence_type == "sendgrid_key":
        # SendGrid: SG.xxx...xxx
        if evidence.startswith("SG."):
            return f"SG.{mask_secret(evidence[3:], visible_chars=3)}"
        return mask_secret(evidence, visible_chars=4)
    
    elif evidence_type == "stripe_key":
        # Stripe: sk_live_xxx...xxx or sk_test_xxx...xxx
        if evidence.startswith(("sk_live_", "sk_test_")):
            prefix = evidence.split("_", 2)[:2]
            prefix_str = "_".join(prefix) + "_"
            return f"{prefix_str}{mask_secret(evidence[len(prefix_str):], visible_chars=3)}"
        return mask_secret(evidence, visible_chars=4)
    
    else:
        # Generic masking
        return mask_secret(evidence, visible_chars=4)


def should_mask_by_default(key: str, value: Any, mask_by_default: bool = True) -> bool:
    """
    Determine if a field should be masked by default based on configuration
    
    Args:
        key: Field/key name
        value: Field value
        mask_by_default: Global masking preference
        
    Returns:
        True if should be masked, False otherwise
    """
    if not mask_by_default:
        return False
    
    # Always mask these sensitive patterns regardless of global setting
    always_mask_keys = ['password', 'secret', 'token', 'key', 'credential', 'bot_token']
    if any(pattern in key.lower() for pattern in always_mask_keys):
        return True
    
    # Check for common credential patterns in values
    if isinstance(value, str):
        # AWS keys
        if re.match(r"AKIA[A-Z0-9]{16}", value):
            return True
        # JWT tokens
        if re.match(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", value):
            return True
        # Base64 encoded (likely credentials if long enough)
        if len(value) > 20 and re.match(r"^[A-Za-z0-9+/]+=*$", value):
            return True
    
    return mask_by_default


class MaskingConfig:
    """Configuration for masking behavior"""
    
    def __init__(
        self,
        mask_by_default: bool = True,
        mask_char: str = "*",
        visible_chars: int = 4,
        always_mask_keys: Optional[List[str]] = None,
        never_mask_keys: Optional[List[str]] = None
    ):
        self.mask_by_default = mask_by_default
        self.mask_char = mask_char
        self.visible_chars = visible_chars
        
        self.always_mask_keys = always_mask_keys or [
            'password', 'secret', 'token', 'key', 'auth', 'credential',
            'bot_token', 'webhook_secret', 'private_key', 'access_key'
        ]
        
        self.never_mask_keys = never_mask_keys or [
            'id', 'name', 'title', 'description', 'status', 'timestamp',
            'created_at', 'updated_at', 'url', 'domain', 'service'
        ]
    
    def should_mask(self, key: str, value: Any) -> bool:
        """Determine if a key/value should be masked based on configuration"""
        key_lower = key.lower()
        
        # Never mask certain keys
        if any(never_key in key_lower for never_key in self.never_mask_keys):
            return False
        
        # Always mask certain keys
        if any(always_key in key_lower for always_key in self.always_mask_keys):
            return True
        
        return should_mask_by_default(key, value, self.mask_by_default)
    
    def mask_value(self, value: str, evidence_type: str = "generic") -> str:
        """Mask a value using configured settings"""
        if evidence_type != "generic":
            return mask_evidence(value, evidence_type)
        return mask_secret(value, self.mask_char, self.visible_chars)


# Global default masking configuration
default_masking_config = MaskingConfig()


def apply_masking(data: Dict[str, Any], config: Optional[MaskingConfig] = None) -> Dict[str, Any]:
    """
    Apply masking to a dictionary using the specified configuration
    
    Args:
        data: Dictionary to mask
        config: Masking configuration (uses default if None)
        
    Returns:
        Dictionary with appropriate values masked
    """
    if config is None:
        config = default_masking_config
    
    def mask_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if isinstance(value, str) and config.should_mask(key, value):
                    result[key] = config.mask_value(value)
                elif isinstance(value, (dict, list)):
                    result[key] = mask_recursive(value)
                else:
                    result[key] = value
            return result
        elif isinstance(obj, list):
            return [mask_recursive(item) for item in obj]
        else:
            return obj
    
    return mask_recursive(data)