"""Environment-based settings using Pydantic BaseSettings"""

import os
import secrets
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import structlog

logger = structlog.get_logger()


def load_yaml_config() -> Dict[str, Any]:
    """Load configuration from data/config.yml"""
    config_path = Path("data/config.yml")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load config.yml", error=str(e))
    return {}


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config files"""
    
    # Security
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="SECRET_KEY")
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Admin User
    admin_email: str = Field(default="admin@example.com", env="ADMIN_EMAIL")
    admin_password: str = Field(default="admin123", env="ADMIN_PASSWORD")
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./httpx_scanner.db", 
        env="DATABASE_URL"
    )
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    use_redis: bool = Field(default=True, env="USE_REDIS")
    
    # CORS
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:8000,http://127.0.0.1:8000", 
        env="CORS_ORIGINS"
    )
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # Scanner Configuration
    max_concurrency: int = Field(default=1000, env="MAX_CONCURRENCY")
    max_scan_retention_days: int = Field(default=30, env="MAX_SCAN_RETENTION_DAYS")
    httpx_path: str = Field(default="httpx", env="HTTPX_PATH")
    
    # Notifications
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    discord_webhook_url: Optional[str] = Field(default=None, env="DISCORD_WEBHOOK_URL")
    webhook_secret: Optional[str] = Field(default=None, env="WEBHOOK_SECRET")
    
    # Development
    debug: bool = Field(default=False, env="DEBUG")
    reload: bool = Field(default=False, env="RELOAD")
    
    # Application State
    first_run: bool = Field(default=True)
    setup_completed: bool = Field(default=False)
    auth_required: bool = Field(default=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from YAML config
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.strip():  # Only split if not empty
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            else:
                return ["http://localhost:8000", "http://127.0.0.1:8000"]  # Default fallback
        elif isinstance(v, list):
            return v
        return ["http://localhost:8000", "http://127.0.0.1:8000"]
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins
    
    @validator("secret_key")
    def validate_secret_key(cls, v, values):
        if v in ["change-me-in-production", "httpx-scanner-change-me-in-production"]:
            logger.warning("Using default secret key - change in production")
        return v
    
    @validator("jwt_secret_key")
    def validate_jwt_secret_key(cls, v, values):
        if not v:
            logger.warning("JWT secret key not provided - using generated key")
        return v

    def __init__(self, **data):
        # Load YAML config first
        yaml_config = load_yaml_config()
        
        # Merge YAML config with provided data, giving precedence to environment variables
        merged_data = {**yaml_config, **data}
        
        # Override first_run and setup_completed from YAML if present
        if 'first_run' in yaml_config:
            merged_data['first_run'] = yaml_config['first_run']
        if 'setup_completed' in yaml_config:
            merged_data['setup_completed'] = yaml_config['setup_completed']
            
        super().__init__(**merged_data)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """Reload settings from files and environment"""
    global _settings
    _settings = None
    return get_settings()


def validate_settings() -> List[str]:
    """Validate settings and return list of issues"""
    settings = get_settings()
    issues = []
    
    # Security validation
    if settings.secret_key in ["change-me-in-production", "httpx-scanner-change-me-in-production"]:
        issues.append("Secret key should be changed from default value")
    
    if settings.admin_password == "admin123":
        issues.append("Admin password should be changed from default value")
    
    # Database validation
    if not settings.database_url:
        issues.append("Database URL not configured")
    
    # Redis validation  
    if settings.use_redis and not settings.redis_url:
        issues.append("Redis is enabled but URL not configured")
    
    # Notification validation
    if settings.telegram_bot_token and not settings.telegram_chat_id:
        issues.append("Telegram bot token provided but chat ID missing")
    
    if settings.telegram_chat_id and not settings.telegram_bot_token:
        issues.append("Telegram chat ID provided but bot token missing")
    
    # Concurrency validation
    if settings.max_concurrency > 50000:
        issues.append("Max concurrency exceeds recommended limit of 50,000")
    
    return issues