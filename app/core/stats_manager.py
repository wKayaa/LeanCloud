"""Real-time statistics manager for httpxCloud v1"""

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Deque
import structlog
from dataclasses import dataclass, field

logger = structlog.get_logger()


@dataclass
class ScanStats:
    """Statistics for a single scan"""
    scan_id: str
    crack_id: str
    status: str = "queued"
    
    # Progress tracking
    processed_urls: int = 0
    total_urls: int = 0
    hits: int = 0
    errors: int = 0
    invalid_urls: int = 0
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Performance metrics
    urls_per_sec: float = 0.0
    checks_per_sec: float = 0.0
    avg_response_time: float = 0.0
    
    # ETA calculation
    eta_seconds: Optional[float] = None
    
    # Moving averages (for smoothing)
    _url_timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    _check_timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    _response_times: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    
    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage"""
        if self.total_urls == 0:
            return 0.0
        return min(100.0, (self.processed_urls / self.total_urls) * 100.0)
    
    @property
    def duration_seconds(self) -> float:
        """Calculate scan duration in seconds"""
        if not self.start_time:
            return 0.0
        end_time = self.end_time or datetime.now(timezone.utc)
        return (end_time - self.start_time).total_seconds()
    
    def update_progress(self, processed: int, total: int = None):
        """Update progress counters"""
        self.processed_urls = processed
        if total is not None:
            self.total_urls = total
        
        # Update URL processing rate
        now = time.time()
        self._url_timestamps.append(now)
        
        # Calculate URLs per second (over last N timestamps)
        if len(self._url_timestamps) >= 2:
            time_window = self._url_timestamps[-1] - self._url_timestamps[0]
            if time_window > 0:
                self.urls_per_sec = (len(self._url_timestamps) - 1) / time_window
        
        # Update ETA
        self._calculate_eta()
        self.last_update = datetime.now(timezone.utc)
    
    def add_check(self, response_time: float = None):
        """Record a check (request) completion"""
        now = time.time()
        self._check_timestamps.append(now)
        
        if response_time is not None:
            self._response_times.append(response_time)
            if self._response_times:
                self.avg_response_time = sum(self._response_times) / len(self._response_times)
        
        # Calculate checks per second
        if len(self._check_timestamps) >= 2:
            time_window = self._check_timestamps[-1] - self._check_timestamps[0]
            if time_window > 0:
                self.checks_per_sec = (len(self._check_timestamps) - 1) / time_window
        
        self.last_update = datetime.now(timezone.utc)
    
    def add_hit(self):
        """Record a hit/finding"""
        self.hits += 1
        self.last_update = datetime.now(timezone.utc)
    
    def add_error(self):
        """Record an error"""
        self.errors += 1
        self.last_update = datetime.now(timezone.utc)
    
    def add_invalid_url(self):
        """Record an invalid URL"""
        self.invalid_urls += 1
        self.last_update = datetime.now(timezone.utc)
    
    def start_scan(self):
        """Mark scan as started"""
        self.status = "running"
        self.start_time = datetime.now(timezone.utc)
        self.last_update = self.start_time
    
    def pause_scan(self):
        """Mark scan as paused"""
        self.status = "paused"
        self.last_update = datetime.now(timezone.utc)
    
    def resume_scan(self):
        """Mark scan as resumed"""
        self.status = "running"
        self.last_update = datetime.now(timezone.utc)
    
    def stop_scan(self):
        """Mark scan as stopped"""
        self.status = "stopped"
        self.end_time = datetime.now(timezone.utc)
        self.last_update = self.end_time
        self.eta_seconds = None
    
    def complete_scan(self):
        """Mark scan as completed"""
        self.status = "completed"
        self.end_time = datetime.now(timezone.utc)
        self.last_update = self.end_time
        self.eta_seconds = None
        self.processed_urls = self.total_urls  # Ensure 100% completion
    
    def _calculate_eta(self):
        """Calculate estimated time to completion"""
        if self.status not in ["running"] or self.total_urls == 0:
            self.eta_seconds = None
            return
        
        remaining_urls = self.total_urls - self.processed_urls
        if remaining_urls <= 0:
            self.eta_seconds = 0
            return
        
        if self.urls_per_sec > 0:
            self.eta_seconds = remaining_urls / self.urls_per_sec
        else:
            self.eta_seconds = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "scan_id": self.scan_id,
            "crack_id": self.crack_id,
            "status": self.status,
            "processed_urls": self.processed_urls,
            "total_urls": self.total_urls,
            "hits": self.hits,
            "errors": self.errors,
            "invalid_urls": self.invalid_urls,
            "progress_percent": self.progress_percent,
            "duration_seconds": self.duration_seconds,
            "urls_per_sec": round(self.urls_per_sec, 2),
            "checks_per_sec": round(self.checks_per_sec, 2),
            "avg_response_time": round(self.avg_response_time, 3),
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds is not None else None,
            "last_update": self.last_update.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


@dataclass 
class GlobalStats:
    """Global system statistics"""
    total_scans: int = 0
    active_scans: int = 0
    completed_scans: int = 0
    total_hits: int = 0
    total_errors: int = 0
    
    # Performance
    total_urls_processed: int = 0
    avg_urls_per_sec: float = 0.0
    avg_checks_per_sec: float = 0.0
    
    # System resources
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_scans": self.total_scans,
            "active_scans": self.active_scans,
            "completed_scans": self.completed_scans,
            "total_hits": self.total_hits,
            "total_errors": self.total_errors,
            "total_urls_processed": self.total_urls_processed,
            "avg_urls_per_sec": round(self.avg_urls_per_sec, 2),
            "avg_checks_per_sec": round(self.avg_checks_per_sec, 2),
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
            "last_update": self.last_update.isoformat()
        }


class StatsManager:
    """
    Real-time statistics manager for httpxCloud v1
    
    Manages scan statistics, performance metrics, and WebSocket broadcasts
    """
    
    def __init__(self):
        self.scan_stats: Dict[str, ScanStats] = {}
        self.global_stats = GlobalStats()
        self._subscribers: Dict[str, List] = defaultdict(list)  # scan_id -> [websockets]
        self._dashboard_subscribers: List = []
        self._stats_history: Deque[Dict[str, Any]] = deque(maxlen=1000)  # Keep last 1000 stat snapshots
        
        # Background task for periodic updates
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the stats manager background tasks"""
        if self._running:
            return
            
        self._running = True
        self._update_task = asyncio.create_task(self._periodic_update())
        logger.info("StatsManager started")
    
    async def stop(self):
        """Stop the stats manager"""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        logger.info("StatsManager stopped")
    
    def create_scan(self, scan_id: str, crack_id: str, total_urls: int = 0) -> ScanStats:
        """Create new scan statistics"""
        stats = ScanStats(
            scan_id=scan_id,
            crack_id=crack_id,
            total_urls=total_urls
        )
        self.scan_stats[scan_id] = stats
        self.global_stats.total_scans += 1
        self.global_stats.last_update = datetime.now(timezone.utc)
        
        logger.info("Created scan stats", scan_id=scan_id, crack_id=crack_id, total_urls=total_urls)
        return stats
    
    def get_scan_stats(self, scan_id: str) -> Optional[ScanStats]:
        """Get scan statistics by ID"""
        return self.scan_stats.get(scan_id)
    
    def update_scan_progress(self, scan_id: str, processed: int, total: int = None):
        """Update scan progress"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        stats.update_progress(processed, total)
        
        # Broadcast to subscribers
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def add_scan_check(self, scan_id: str, response_time: float = None):
        """Record a check/request for a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        stats.add_check(response_time)
    
    def add_scan_hit(self, scan_id: str):
        """Record a hit/finding for a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        stats.add_hit()
        self.global_stats.total_hits += 1
        
        # Broadcast to subscribers
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def add_scan_error(self, scan_id: str):
        """Record an error for a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        stats.add_error()
        self.global_stats.total_errors += 1
        
        # Broadcast to subscribers
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def start_scan(self, scan_id: str):
        """Start a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        stats.start_scan()
        self.global_stats.active_scans += 1
        
        logger.info("Scan started", scan_id=scan_id)
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def pause_scan(self, scan_id: str):
        """Pause a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        if stats.status == "running":
            stats.pause_scan()
            self.global_stats.active_scans -= 1
        
        logger.info("Scan paused", scan_id=scan_id)
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def resume_scan(self, scan_id: str):
        """Resume a paused scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        if stats.status == "paused":
            stats.resume_scan()
            self.global_stats.active_scans += 1
        
        logger.info("Scan resumed", scan_id=scan_id)
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def stop_scan(self, scan_id: str):
        """Stop a scan"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        if stats.status in ["running", "paused"]:
            stats.stop_scan()
            if stats.status == "running":
                self.global_stats.active_scans -= 1
        
        logger.info("Scan stopped", scan_id=scan_id)
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def complete_scan(self, scan_id: str):
        """Mark scan as completed"""
        if scan_id not in self.scan_stats:
            return
        
        stats = self.scan_stats[scan_id]
        if stats.status == "running":
            self.global_stats.active_scans -= 1
        
        stats.complete_scan()
        self.global_stats.completed_scans += 1
        self.global_stats.total_urls_processed += stats.processed_urls
        
        logger.info("Scan completed", scan_id=scan_id, 
                   processed=stats.processed_urls, hits=stats.hits)
        asyncio.create_task(self._broadcast_scan_update(scan_id))
    
    def subscribe_to_scan(self, scan_id: str, websocket):
        """Subscribe a WebSocket to scan updates"""
        self._subscribers[scan_id].append(websocket)
        logger.debug("WebSocket subscribed to scan", scan_id=scan_id)
    
    def unsubscribe_from_scan(self, scan_id: str, websocket):
        """Unsubscribe a WebSocket from scan updates"""
        if scan_id in self._subscribers and websocket in self._subscribers[scan_id]:
            self._subscribers[scan_id].remove(websocket)
            logger.debug("WebSocket unsubscribed from scan", scan_id=scan_id)
    
    def subscribe_to_dashboard(self, websocket):
        """Subscribe a WebSocket to dashboard updates"""
        self._dashboard_subscribers.append(websocket)
        logger.debug("WebSocket subscribed to dashboard")
    
    def unsubscribe_from_dashboard(self, websocket):
        """Unsubscribe a WebSocket from dashboard updates"""
        if websocket in self._dashboard_subscribers:
            self._dashboard_subscribers.remove(websocket)
            logger.debug("WebSocket unsubscribed from dashboard")
    
    async def _broadcast_scan_update(self, scan_id: str):
        """Broadcast scan update to subscribers"""
        if scan_id not in self._subscribers:
            return
        
        stats = self.scan_stats.get(scan_id)
        if not stats:
            return
        
        message = {
            "type": "scan.progress",
            "scan_id": scan_id,
            "data": stats.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Remove closed WebSockets and send to active ones
        active_subscribers = []
        for ws in self._subscribers[scan_id]:
            try:
                await ws.send_json(message)
                active_subscribers.append(ws)
            except Exception as e:
                logger.debug("Failed to send to WebSocket", error=str(e))
        
        self._subscribers[scan_id] = active_subscribers
    
    async def _broadcast_dashboard_update(self):
        """Broadcast dashboard update to subscribers"""
        if not self._dashboard_subscribers:
            return
        
        # Update global stats
        self._update_global_stats()
        
        message = {
            "type": "dashboard.stats",
            "data": self.global_stats.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Store in history
        self._stats_history.append(message["data"])
        
        # Remove closed WebSockets and send to active ones
        active_subscribers = []
        for ws in self._dashboard_subscribers:
            try:
                await ws.send_json(message)
                active_subscribers.append(ws)
            except Exception as e:
                logger.debug("Failed to send to dashboard WebSocket", error=str(e))
        
        self._dashboard_subscribers = active_subscribers
    
    def _update_global_stats(self):
        """Update global statistics from scan statistics"""
        active_count = 0
        total_urls_per_sec = 0.0
        total_checks_per_sec = 0.0
        active_scans = 0
        
        for stats in self.scan_stats.values():
            if stats.status == "running":
                active_count += 1
                total_urls_per_sec += stats.urls_per_sec
                total_checks_per_sec += stats.checks_per_sec
        
        self.global_stats.active_scans = active_count
        self.global_stats.avg_urls_per_sec = total_urls_per_sec
        self.global_stats.avg_checks_per_sec = total_checks_per_sec
        self.global_stats.last_update = datetime.now(timezone.utc)
        
        # TODO: Update system resource metrics (CPU, memory)
        # This would require psutil integration
    
    async def _periodic_update(self):
        """Periodic background update task"""
        while self._running:
            try:
                await self._broadcast_dashboard_update()
                await asyncio.sleep(2)  # Update dashboard every 2 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic update", error=str(e))
                await asyncio.sleep(5)  # Wait longer on error
    
    def get_stats_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent statistics history"""
        return list(self._stats_history)[-limit:]
    
    def cleanup_old_scans(self, max_age_hours: int = 24):
        """Clean up old scan statistics to prevent memory leaks"""
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for scan_id, stats in self.scan_stats.items():
            if stats.status in ["completed", "stopped"] and stats.end_time:
                age_hours = (now - stats.end_time).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(scan_id)
        
        for scan_id in to_remove:
            del self.scan_stats[scan_id]
            if scan_id in self._subscribers:
                del self._subscribers[scan_id]
            logger.info("Cleaned up old scan stats", scan_id=scan_id)


# Global stats manager instance
stats_manager = StatsManager()