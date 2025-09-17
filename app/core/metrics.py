"""Prometheus metrics for httpxCloud v1"""

import time
from typing import Dict, Any
from prometheus_client import (
    Counter, Histogram, Gauge, Info, generate_latest, 
    CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY
)
import structlog

logger = structlog.get_logger()


class HTTPxMetrics:
    """Prometheus metrics for HTTPx Scanner"""
    
    def __init__(self, registry: CollectorRegistry = REGISTRY):
        self.registry = registry
        
        # Service info
        self.service_info = Info(
            'httpx_scanner_info',
            'HTTPx Scanner service information',
            registry=self.registry
        )
        self.service_info.info({
            'version': '1.0.0',
            'component': 'httpx_scanner'
        })
        
        # Scan metrics
        self.scans_total = Counter(
            'httpx_scans_total',
            'Total number of scans',
            ['status'],
            registry=self.registry
        )
        
        self.scans_active = Gauge(
            'httpx_scans_active',
            'Number of currently active scans',
            registry=self.registry
        )
        
        self.scan_duration = Histogram(
            'httpx_scan_duration_seconds',
            'Scan duration in seconds',
            ['status'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=self.registry
        )
        
        self.scan_targets = Histogram(
            'httpx_scan_targets',
            'Number of targets per scan',
            buckets=[1, 5, 10, 20, 50, 100, 200, 500, 1000],
            registry=self.registry
        )
        
        self.scan_urls_generated = Histogram(
            'httpx_scan_urls_generated',
            'Number of URLs generated per scan',
            buckets=[10, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
            registry=self.registry
        )
        
        # HTTP request metrics
        self.http_requests_total = Counter(
            'httpx_http_requests_total',
            'Total number of HTTP requests',
            ['method', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'httpx_http_request_duration_seconds',
            'HTTP request duration in seconds',
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.http_requests_active = Gauge(
            'httpx_http_requests_active',
            'Number of currently active HTTP requests',
            registry=self.registry
        )
        
        # Finding metrics
        self.findings_total = Counter(
            'httpx_findings_total',
            'Total number of findings',
            ['service', 'severity', 'works'],
            registry=self.registry
        )
        
        self.findings_per_scan = Histogram(
            'httpx_findings_per_scan',
            'Number of findings per scan',
            buckets=[0, 1, 5, 10, 25, 50, 100, 200, 500],
            registry=self.registry
        )
        
        # Performance metrics
        self.checks_per_second = Gauge(
            'httpx_checks_per_second',
            'Current checks per second rate',
            ['scan_id'],
            registry=self.registry
        )
        
        self.urls_per_second = Gauge(
            'httpx_urls_per_second',
            'Current URLs per second rate',
            ['scan_id'],
            registry=self.registry
        )
        
        self.concurrency_current = Gauge(
            'httpx_concurrency_current',
            'Current concurrency level',
            ['scan_id'],
            registry=self.registry
        )
        
        self.concurrency_max = Gauge(
            'httpx_concurrency_max',
            'Maximum concurrency level',
            ['scan_id'],
            registry=self.registry
        )
        
        # Resource usage metrics
        self.cpu_usage_percent = Gauge(
            'httpx_cpu_usage_percent',
            'CPU usage percentage',
            ['scan_id'],
            registry=self.registry
        )
        
        self.memory_usage_bytes = Gauge(
            'httpx_memory_usage_bytes',
            'Memory usage in bytes',
            ['scan_id'],
            registry=self.registry
        )
        
        self.network_bytes_sent = Counter(
            'httpx_network_bytes_sent_total',
            'Total network bytes sent',
            ['scan_id'],
            registry=self.registry
        )
        
        self.network_bytes_received = Counter(
            'httpx_network_bytes_received_total',
            'Total network bytes received',
            ['scan_id'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'httpx_errors_total',
            'Total number of errors',
            ['error_type', 'scan_id'],
            registry=self.registry
        )
        
        self.timeouts_total = Counter(
            'httpx_timeouts_total',
            'Total number of timeouts',
            ['scan_id'],
            registry=self.registry
        )
        
        self.circuit_breaker_trips = Counter(
            'httpx_circuit_breaker_trips_total',
            'Total number of circuit breaker trips',
            ['host'],
            registry=self.registry
        )
        
        # Queue metrics
        self.queue_size = Gauge(
            'httpx_queue_size',
            'Current queue size',
            ['scan_id', 'queue_type'],
            registry=self.registry
        )
        
        self.queue_processing_time = Histogram(
            'httpx_queue_processing_time_seconds',
            'Time spent processing queue items',
            ['queue_type'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        # Database metrics
        self.database_queries_total = Counter(
            'httpx_database_queries_total',
            'Total number of database queries',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.database_query_duration = Histogram(
            'httpx_database_query_duration_seconds',
            'Database query duration in seconds',
            ['operation', 'table'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry
        )
        
        self.database_connections_active = Gauge(
            'httpx_database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        # WebSocket metrics
        self.websocket_connections_active = Gauge(
            'httpx_websocket_connections_active',
            'Number of active WebSocket connections',
            registry=self.registry
        )
        
        self.websocket_messages_sent = Counter(
            'httpx_websocket_messages_sent_total',
            'Total number of WebSocket messages sent',
            ['event_type'],
            registry=self.registry
        )
        
        self.websocket_messages_received = Counter(
            'httpx_websocket_messages_received_total',
            'Total number of WebSocket messages received',
            ['message_type'],
            registry=self.registry
        )
        
        # Notification metrics
        self.notifications_sent = Counter(
            'httpx_notifications_sent_total',
            'Total number of notifications sent',
            ['channel', 'success'],
            registry=self.registry
        )
        
        self.notification_duration = Histogram(
            'httpx_notification_duration_seconds',
            'Notification sending duration in seconds',
            ['channel'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        logger.info("Prometheus metrics initialized")
    
    # Scan lifecycle methods
    def scan_started(self, scan_id: str, targets_count: int, urls_count: int, concurrency: int):
        """Record scan started"""
        self.scans_total.labels(status='started').inc()
        self.scans_active.inc()
        self.scan_targets.observe(targets_count)
        self.scan_urls_generated.observe(urls_count)
        self.concurrency_max.labels(scan_id=scan_id).set(concurrency)
    
    def scan_completed(self, scan_id: str, status: str, duration: float, findings_count: int):
        """Record scan completed"""
        self.scans_total.labels(status=status).inc()
        self.scans_active.dec()
        self.scan_duration.labels(status=status).observe(duration)
        self.findings_per_scan.observe(findings_count)
        
        # Clear scan-specific metrics
        self._clear_scan_metrics(scan_id)
    
    def _clear_scan_metrics(self, scan_id: str):
        """Clear metrics for a specific scan"""
        try:
            # Remove scan-specific gauge metrics
            self.checks_per_second._metrics.pop((scan_id,), None)
            self.urls_per_second._metrics.pop((scan_id,), None)
            self.concurrency_current._metrics.pop((scan_id,), None)
            self.concurrency_max._metrics.pop((scan_id,), None)
            self.cpu_usage_percent._metrics.pop((scan_id,), None)
            self.memory_usage_bytes._metrics.pop((scan_id,), None)
        except Exception as e:
            logger.warning("Failed to clear scan metrics", scan_id=scan_id, error=str(e))
    
    # HTTP request methods
    def http_request_started(self):
        """Record HTTP request started"""
        self.http_requests_active.inc()
    
    def http_request_completed(self, method: str, status_code: int, duration: float):
        """Record HTTP request completed"""
        self.http_requests_active.dec()
        self.http_requests_total.labels(method=method, status_code=str(status_code)).inc()
        self.http_request_duration.observe(duration)
    
    def http_request_timeout(self, scan_id: str):
        """Record HTTP request timeout"""
        self.timeouts_total.labels(scan_id=scan_id).inc()
        self.errors_total.labels(error_type='timeout', scan_id=scan_id).inc()
    
    # Finding methods
    def finding_created(self, service: str, severity: str, works: bool):
        """Record finding created"""
        self.findings_total.labels(
            service=service,
            severity=severity,
            works=str(works).lower()
        ).inc()
    
    # Performance methods
    def update_performance_metrics(self, scan_id: str, checks_per_sec: float, urls_per_sec: float, 
                                 concurrency: int):
        """Update performance metrics"""
        self.checks_per_second.labels(scan_id=scan_id).set(checks_per_sec)
        self.urls_per_second.labels(scan_id=scan_id).set(urls_per_sec)
        self.concurrency_current.labels(scan_id=scan_id).set(concurrency)
    
    # Resource usage methods
    def update_resource_usage(self, scan_id: str, cpu_percent: float, memory_bytes: float):
        """Update resource usage metrics"""
        self.cpu_usage_percent.labels(scan_id=scan_id).set(cpu_percent)
        self.memory_usage_bytes.labels(scan_id=scan_id).set(memory_bytes)
    
    def update_network_usage(self, scan_id: str, bytes_sent: int, bytes_received: int):
        """Update network usage metrics"""
        self.network_bytes_sent.labels(scan_id=scan_id).inc(bytes_sent)
        self.network_bytes_received.labels(scan_id=scan_id).inc(bytes_received)
    
    # Error methods
    def record_error(self, error_type: str, scan_id: str):
        """Record error"""
        self.errors_total.labels(error_type=error_type, scan_id=scan_id).inc()
    
    def circuit_breaker_tripped(self, host: str):
        """Record circuit breaker trip"""
        self.circuit_breaker_trips.labels(host=host).inc()
    
    # Queue methods
    def update_queue_size(self, scan_id: str, queue_type: str, size: int):
        """Update queue size"""
        self.queue_size.labels(scan_id=scan_id, queue_type=queue_type).set(size)
    
    def record_queue_processing_time(self, queue_type: str, duration: float):
        """Record queue processing time"""
        self.queue_processing_time.labels(queue_type=queue_type).observe(duration)
    
    # Database methods
    def database_query_started(self, operation: str, table: str):
        """Record database query started"""
        self.database_queries_total.labels(operation=operation, table=table).inc()
    
    def database_query_completed(self, operation: str, table: str, duration: float):
        """Record database query completed"""
        self.database_query_duration.labels(operation=operation, table=table).observe(duration)
    
    def update_database_connections(self, active_connections: int):
        """Update active database connections"""
        self.database_connections_active.set(active_connections)
    
    # WebSocket methods
    def websocket_connected(self):
        """Record WebSocket connection"""
        self.websocket_connections_active.inc()
    
    def websocket_disconnected(self):
        """Record WebSocket disconnection"""
        self.websocket_connections_active.dec()
    
    def websocket_message_sent(self, event_type: str):
        """Record WebSocket message sent"""
        self.websocket_messages_sent.labels(event_type=event_type).inc()
    
    def websocket_message_received(self, message_type: str):
        """Record WebSocket message received"""
        self.websocket_messages_received.labels(message_type=message_type).inc()
    
    # Notification methods
    def notification_sent(self, channel: str, success: bool, duration: float):
        """Record notification sent"""
        self.notifications_sent.labels(channel=channel, success=str(success).lower()).inc()
        self.notification_duration.labels(channel=channel).observe(duration)
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get Prometheus metrics content type"""
        return CONTENT_TYPE_LATEST


# Global metrics instance
metrics = HTTPxMetrics()


class MetricsTimer:
    """Context manager for timing operations"""
    
    def __init__(self, histogram, labels: Dict[str, str] = None):
        self.histogram = histogram
        self.labels = labels or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            if self.labels:
                self.histogram.labels(**self.labels).observe(duration)
            else:
                self.histogram.observe(duration)


def time_database_query(operation: str, table: str):
    """Time database query"""
    return MetricsTimer(
        metrics.database_query_duration,
        {'operation': operation, 'table': table}
    )


def time_http_request():
    """Time HTTP request"""
    return MetricsTimer(metrics.http_request_duration)


def time_notification(channel: str):
    """Time notification"""
    return MetricsTimer(
        metrics.notification_duration,
        {'channel': channel}
    )


def time_queue_processing(queue_type: str):
    """Time queue processing"""
    return MetricsTimer(
        metrics.queue_processing_time,
        {'queue_type': queue_type}
    )