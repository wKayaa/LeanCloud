from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import uuid


class ScanStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ModuleType(str, Enum):
    AWS = "aws"
    SENDGRID = "sendgrid"
    SMTP = "smtp"
    MAILGUN = "mailgun"
    TWILIO = "twilio"
    DOCKER = "docker"
    K8S = "k8s"
    STRIPE = "stripe"
    GENERIC = "generic"


class ScanRequest(BaseModel):
    targets: List[str] = Field(..., description="List of target URLs/domains")
    wordlist: str = Field(default="paths.txt", description="Wordlist filename")
    modules: List[ModuleType] = Field(default=[], description="Modules to scan with")
    concurrency: int = Field(default=50, ge=1, le=50000, description="Number of concurrent threads")
    rate_limit: int = Field(default=100, description="Requests per second")
    timeout: int = Field(default=10, description="Request timeout in seconds")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    regex_rules: List[str] = Field(default=[], description="Custom regex patterns")
    path_rules: List[str] = Field(default=[], description="Custom path patterns")
    notes: Optional[str] = Field(default=None, description="Scan notes")

    @validator('concurrency')
    def validate_concurrency(cls, v):
        if v > 50000:
            raise ValueError('Concurrency cannot exceed 50,000 for safety')
        return v


class SecretPattern(BaseModel):
    name: str
    pattern: str
    description: str
    module_type: ModuleType = ModuleType.GENERIC


class Finding(BaseModel):
    id: str
    scan_id: str
    crack_id: str  # Human-readable scan identifier
    service: str  # Service type (AWS, SendGrid, etc.)
    pattern_id: str
    url: str
    source_url: str  # Original URL that led to finding
    first_seen: datetime
    last_seen: datetime
    evidence: str
    evidence_masked: str
    works: bool = False  # Whether credentials work
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)  # Confidence score
    severity: str = Field(default="medium")  # low, medium, high, critical
    regions: List[str] = Field(default=[])  # Applicable regions
    capabilities: List[str] = Field(default=[])  # Service capabilities
    quotas: Dict[str, Any] = Field(default={})  # Service quotas/limits
    verified_identities: List[str] = Field(default=[])  # Verified identities
    created_at: datetime = Field(default_factory=datetime.now)


class ScanResult(BaseModel):
    id: str
    crack_id: str  # Human-readable identifier
    status: ScanStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    targets: List[str]
    total_urls: int = 0
    processed_urls: int = 0
    checked_paths: int = 0
    checked_urls: int = 0
    invalid_urls: int = 0
    findings_count: int = 0
    hits_count: int = 0
    errors_count: int = 0
    docker_infected: int = 0  # Docker containers infected
    k8s_infected: int = 0     # K8s pods infected
    error_message: Optional[str] = None
    config: ScanRequest
    
    # Live metrics
    checks_per_sec: float = 0.0
    urls_per_sec: float = 0.0
    eta_seconds: Optional[int] = None
    progress_percent: float = 0.0
    
    # Resource usage
    cpu_percent: float = 0.0
    ram_mb: float = 0.0
    net_mbps_in: float = 0.0
    net_mbps_out: float = 0.0


class ScanStats(BaseModel):
    """Real-time scan statistics"""
    scan_id: str
    crack_id: str
    status: ScanStatus
    progress_pct: float
    eta: Optional[int]  # seconds
    checks_sec: float
    urls_sec: float
    checked_paths: int
    checked_urls: int
    invalid_urls: int
    total_urls: int
    hits: int
    errors: int
    docker_infected: int
    k8s_infected: int
    timestamp: datetime = Field(default_factory=datetime.now)


class ScanResourceUsage(BaseModel):
    """Resource usage metrics"""
    scan_id: str
    cpu_pct: float
    ram_mb: float
    net_mbps_in: float
    net_mbps_out: float
    timestamp: datetime = Field(default_factory=datetime.now)


class ConfigModel(BaseModel):
    auth_required: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-production") 
    first_run: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60)
    max_scan_retention_days: int = Field(default=30)
    httpx_path: str = Field(default="httpx")
    default_patterns: List[SecretPattern] = Field(default_factory=list)
    
    # New v1 config options
    max_concurrency: int = Field(default=50000)
    adaptive_concurrency: bool = Field(default=True)
    enable_backpressure: bool = Field(default=True)
    queue_max_size: int = Field(default=100000)
    batch_size: int = Field(default=1000)
    
    # Database settings
    database_url: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default="redis://localhost:6379")
    
    # Notification settings
    telegram_bot_token: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    slack_webhook_url: Optional[str] = Field(default=None)
    discord_webhook_url: Optional[str] = Field(default=None)
    webhook_secret: Optional[str] = Field(default=None)


class NotificationConfig(BaseModel):
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    discord_enabled: bool = False
    discord_webhook_url: Optional[str] = None
    webhooks_enabled: bool = False
    webhook_urls: List[str] = Field(default=[])
    webhook_secret: Optional[str] = None


class UserPreferences(BaseModel):
    expert_mode: bool = False
    mask_by_default: bool = True
    auto_refresh_interval: int = Field(default=5000, ge=1000)  # milliseconds
    results_per_page: int = Field(default=50, ge=10, le=1000)
    default_modules: List[ModuleType] = Field(default=[])


class User(BaseModel):
    username: str
    role: str = "admin"  # admin or viewer
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)


class AuthRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class HitExportRequest(BaseModel):
    format: str = Field(regex="^(csv|jsonl)$")
    reveal: bool = False
    scan_ids: Optional[List[str]] = None
    service_filter: Optional[str] = None
    works_filter: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ScanControlRequest(BaseModel):
    action: str = Field(regex="^(start|pause|resume|stop)$")


class WebSocketMessage(BaseModel):
    type: str
    scan_id: Optional[str] = None
    data: Dict[str, Any] = Field(default={})
    timestamp: datetime = Field(default_factory=datetime.now)


# WebSocket event types
class WSEventType(str, Enum):
    # Scan events
    SCAN_STATUS = "scan.status"
    SCAN_PROGRESS = "scan.progress" 
    SCAN_RESOURCES = "scan.resources"
    SCAN_HIT = "scan.hit"
    SCAN_LOG = "scan.log"
    SCAN_SUMMARY = "scan.summary"
    
    # Dashboard events
    DASHBOARD_STATS = "dashboard.stats"
    DASHBOARD_TRENDS = "dashboard.trends"
    
    # Client events
    SUBSCRIBE_SCAN = "subscribe_scan"
    GET_SCAN_STATUS = "get_scan_status"
    PING = "ping"
    PONG = "pong"


class ValidationResult(BaseModel):
    """Result from service validation"""
    works: bool
    confidence: float = Field(ge=0.0, le=1.0)
    regions: List[str] = Field(default=[])
    capabilities: List[str] = Field(default=[])
    quotas: Dict[str, Any] = Field(default={})
    verified_identities: List[str] = Field(default=[])
    error_message: Optional[str] = None


class ModuleResult(BaseModel):
    """Result from a module scan"""
    module_type: ModuleType
    patterns_matched: int
    validation_result: Optional[ValidationResult] = None
    processing_time: float  # seconds