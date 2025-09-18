"""Database configuration and models using SQLAlchemy 2.0 async"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, Float, 
    JSON, ForeignKey, Index, create_engine
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import structlog

logger = structlog.get_logger()

Base = declarative_base()

class ScanDB(Base):
    """Database model for scans"""
    __tablename__ = "scans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crack_id = Column(String(32), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration
    targets = Column(JSON, nullable=False)  # SQLite compatible JSON field
    wordlist = Column(String(255), nullable=False)
    modules = Column(JSON, default=lambda: [])  # SQLite compatible JSON field
    concurrency = Column(Integer, default=50)
    rate_limit = Column(Integer, default=100)
    timeout = Column(Integer, default=10)
    follow_redirects = Column(Boolean, default=True)
    regex_rules = Column(JSON, default=lambda: [])  # SQLite compatible JSON field
    path_rules = Column(JSON, default=lambda: [])  # SQLite compatible JSON field
    notes = Column(Text, nullable=True)
    
    # Stats
    total_urls = Column(Integer, default=0)
    processed_urls = Column(Integer, default=0)
    checked_paths = Column(Integer, default=0)
    checked_urls = Column(Integer, default=0)
    invalid_urls = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    hits_count = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    docker_infected = Column(Integer, default=0)
    k8s_infected = Column(Integer, default=0)
    
    # Live metrics
    checks_per_sec = Column(Float, default=0.0)
    urls_per_sec = Column(Float, default=0.0)
    eta_seconds = Column(Integer, nullable=True)
    progress_percent = Column(Float, default=0.0)
    
    # Resource usage
    cpu_percent = Column(Float, default=0.0)
    ram_mb = Column(Float, default=0.0)
    net_mbps_in = Column(Float, default=0.0)
    net_mbps_out = Column(Float, default=0.0)
    
    error_message = Column(Text, nullable=True)
    
    # Relationships
    findings = relationship("FindingDB", back_populates="scan", cascade="all, delete-orphan")
    events = relationship("EventDB", back_populates="scan", cascade="all, delete-orphan")


class FindingDB(Base):
    """Database model for findings/hits"""
    __tablename__ = "findings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False, index=True)
    crack_id = Column(String(32), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)
    pattern_id = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    source_url = Column(Text, nullable=False)
    
    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    evidence = Column(Text, nullable=False)
    evidence_masked = Column(Text, nullable=False)
    
    works = Column(Boolean, default=False, index=True)
    confidence = Column(Float, default=0.5)
    severity = Column(String(20), default="medium", index=True)
    
    # Enhanced fields for cloud services
    regions = Column(JSON, default=lambda: [])
    capabilities = Column(JSON, default=lambda: [])
    quotas = Column(JSON, default=lambda: {})
    verified_identities = Column(JSON, default=lambda: [])
    
    # Relationships
    scan = relationship("ScanDB", back_populates="findings")


class ListDB(Base):
    """Database model for wordlists and target lists"""
    __tablename__ = "lists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    list_type = Column(String(50), nullable=False, index=True)  # 'wordlist', 'targets', 'ips'
    size = Column(Integer, default=0)  # Number of items
    file_size = Column(Integer, default=0)  # File size in bytes
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    use_count = Column(Integer, default=0)


class IPListDB(Base):
    """Database model for generated IP lists"""
    __tablename__ = "ip_lists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    generator_type = Column(String(50), nullable=False)  # 'random', 'subnet', 'range'
    config = Column(JSON, nullable=False)  # Generator configuration
    ip_count = Column(Integer, default=0)
    unique_ips = Column(JSON, default=lambda: [])  # Store generated IPs
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    status = Column(String(20), default="ready")  # 'generating', 'ready', 'error'


class SettingsDB(Base):
    """Database model for application settings"""
    __tablename__ = "settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(50), nullable=False, index=True)  # 'notifications', 'scan_defaults', 'ui'
    key = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EventDB(Base):
    """Database model for events (WebSocket and notifications)"""
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    scan = relationship("ScanDB", back_populates="events")


class AuditLogDB(Base):
    """Database model for audit logs"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class StatSnapshotDB(Base):
    """Database model for stats snapshots"""
    __tablename__ = "stat_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=True, index=True)
    snapshot_type = Column(String(50), nullable=False, index=True)  # 'scan', 'global', 'service'
    metrics = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# Create indexes for performance
Index('idx_scans_status_created', ScanDB.status, ScanDB.created_at)
Index('idx_findings_scan_service', FindingDB.scan_id, FindingDB.service)
Index('idx_findings_works_confidence', FindingDB.works, FindingDB.confidence)
Index('idx_lists_type_name', ListDB.list_type, ListDB.name)
Index('idx_settings_category_key', SettingsDB.category, SettingsDB.key)
Index('idx_audit_action_created', AuditLogDB.action, AuditLogDB.created_at)


# Global variables
async_engine = None
async_session_factory = None


async def init_database(database_url: str = "sqlite+aiosqlite:///./httpx_scanner.db"):
    """Initialize the database"""
    global async_engine, async_session_factory
    
    try:
        logger.info("Initializing database", url=database_url)
        
        # Create async engine
        async_engine = create_async_engine(
            database_url,
            echo=False,
            future=True
        )
        
        # Create session factory
        async_session_factory = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create all tables
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise


async def get_db_session():
    """Get database session as dependency"""
    if not async_session_factory:
        raise RuntimeError("Database not initialized")
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_async_session():
    """Get async session factory for direct usage"""
    if not async_session_factory:
        raise RuntimeError("Database not initialized")
    return async_session_factory


async def cleanup_database():
    """Cleanup database connections"""
    global async_engine
    if async_engine:
        await async_engine.dispose()
        logger.info("Database connections closed")