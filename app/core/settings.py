"""Environment-based settings using Pydantic BaseSettings"""

import os
import secrets
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import structlog

logger = structlog.get_logger()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
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
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"], 
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
    auth_required: bool = Field(default=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
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


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


def validate_settings() -> List[str]:
    """Validate settings and return list of issues"""
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
    if not settings.redis_url:
        issues.append("Redis URL not configured")
    
    # Notification validation
    if settings.telegram_bot_token and not settings.telegram_chat_id:
        issues.append("Telegram bot token provided but chat ID missing")
    
    if settings.telegram_chat_id and not settings.telegram_bot_token:
        issues.append("Telegram chat ID provided but bot token missing")
    
    # Concurrency validation
    if settings.max_concurrency > 50000:
        issues.append("Max concurrency exceeds recommended limit of 50,000")
    
    return issues