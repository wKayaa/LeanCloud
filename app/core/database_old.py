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
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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
    
    regions = Column(ARRAY(String), default=[])
    capabilities = Column(ARRAY(String), default=[])
    quotas = Column(JSON, default={})
    verified_identities = Column(ARRAY(String), default=[])
    
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


class EventDB(Base):
Index('idx_scans_status_created', ScanDB.status, ScanDB.created_at)
Index('idx_findings_scan_service', FindingDB.scan_id, FindingDB.service)
Index('idx_findings_works_confidence', FindingDB.works, FindingDB.confidence)
Index('idx_lists_type_name', ListDB.list_type, ListDB.name)
Index('idx_settings_category_key', SettingsDB.category, SettingsDB.key)
Index('idx_audit_action_created', AuditLogDB.action, AuditLogDB.created_at)
    """Database model for events (WebSocket and notifications)"""
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    scan = relationship("ScanDB", back_populates="events")


class SettingsDB(Base):
    """Database model for application settings"""
    __tablename__ = "settings"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PresetDB(Base):
    """Database model for scan presets"""
    __tablename__ = "presets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WordlistDB(Base):
    """Database model for uploaded wordlists"""
    __tablename__ = "wordlists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    paths_count = Column(Integer, nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    

class AuditLogDB(Base):
    """Database model for audit logs"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=True)
    scan_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# Create indexes for performance
Index('idx_findings_scan_service', FindingDB.scan_id, FindingDB.service)
Index('idx_findings_works_created', FindingDB.works, FindingDB.created_at)
Index('idx_scans_status_created', ScanDB.status, ScanDB.created_at)
Index('idx_events_scan_type_created', EventDB.scan_id, EventDB.event_type, EventDB.created_at)
Index('idx_audit_logs_action_created', AuditLogDB.action, AuditLogDB.created_at)


class DatabaseManager:
    """Database manager for async operations"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.async_session = None
        
    async def initialize(self):
        """Initialize database connection"""
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            self.async_session = async_sessionmaker(
                self.engine, 
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("Database connection initialized", url=self.database_url.split("@")[-1])
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def create_tables(self):
        """Create database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Failed to create database tables", error=str(e))
            raise
    
    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")
    
    def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.async_session:
            raise RuntimeError("Database not initialized")
        return self.async_session()


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


async def get_db_session() -> AsyncSession:
    """Dependency to get database session"""
    if not db_manager:
        raise RuntimeError("Database manager not initialized")
    
    session = db_manager.get_session() 
    try:
        yield session
    finally:
        await session.close()


async def init_database(database_url: str):
    """Initialize database connection"""
    global db_manager
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize()
    await db_manager.create_tables()


async def close_database():
    """Close database connection"""
    global db_manager
    if db_manager:
        await db_manager.close()
        db_manager = None