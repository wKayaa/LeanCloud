from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ScanStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ScanRequest(BaseModel):
    targets: List[str] = Field(..., description="List of target URLs/domains")
    wordlist: str = Field(default="paths.txt", description="Wordlist filename")
    concurrency: int = Field(default=50, description="Number of concurrent threads")
    rate_limit: int = Field(default=100, description="Requests per second")
    timeout: int = Field(default=10, description="Request timeout in seconds")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")


class SecretPattern(BaseModel):
    name: str
    pattern: str
    description: str


class Finding(BaseModel):
    id: str
    scan_id: str
    provider: str
    pattern_id: str
    url: str
    first_seen: datetime
    last_seen: datetime
    evidence: str
    evidence_masked: str


class ScanResult(BaseModel):
    id: str
    status: ScanStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    targets: List[str]
    total_urls: int = 0
    processed_urls: int = 0
    findings_count: int = 0
    error_message: Optional[str] = None
    config: ScanRequest


class ConfigModel(BaseModel):
    auth_required: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-production")
    first_run: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60)
    max_scan_retention_days: int = Field(default=30)
    httpx_path: str = Field(default="httpx")
    default_patterns: List[SecretPattern] = Field(default_factory=list)


class User(BaseModel):
    username: str
    role: str = "admin"  # admin or viewer
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None


class AuthRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str