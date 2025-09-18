"""Enhanced scanner with high concurrency support for httpxCloud v1"""

import asyncio
import httpx
import time
import uuid
import re
import psutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, AsyncGenerator, Set
from pathlib import Path
import tempfile
import json
from asyncio_throttle import Throttler

import structlog
from .models import (
    ScanRequest, ScanResult, ScanStatus, Finding, SecretPattern, 
    ScanStats, ScanResourceUsage, ModuleType, ValidationResult,
    ModuleResult, WSEventType
)
from .config import config_manager
from .httpx_executor import httpx_executor

logger = structlog.get_logger()


class ConcurrencyManager:
    """Manages adaptive concurrency and backpressure"""
    
    def __init__(self, initial_concurrency: int = 50, max_concurrency: int = 50000):
        self.current_concurrency = initial_concurrency
        self.max_concurrency = max_concurrency
        self.min_concurrency = 10
        self.success_count = 0
        self.error_count = 0
        self.last_adjustment = time.time()
        self.adjustment_interval = 10  # seconds
        
    def adjust_concurrency(self):
        """Adjust concurrency based on success/error rate"""
        now = time.time()
        if now - self.last_adjustment < self.adjustment_interval:
            return
        
        total_requests = self.success_count + self.error_count
        if total_requests == 0:
            return
            
        error_rate = self.error_count / total_requests
        
        if error_rate < 0.01:  # < 1% error rate - increase concurrency
            self.current_concurrency = min(
                int(self.current_concurrency * 1.2), 
                self.max_concurrency
            )
        elif error_rate > 0.05:  # > 5% error rate - decrease concurrency
            self.current_concurrency = max(
                int(self.current_concurrency * 0.8), 
                self.min_concurrency
            )
        
        # Reset counters
        self.success_count = 0
        self.error_count = 0
        self.last_adjustment = now
        
        logger.info("Concurrency adjusted", 
                   concurrency=self.current_concurrency, 
                   error_rate=error_rate)
    
    def record_success(self):
        """Record successful request"""
        self.success_count += 1
    
    def record_error(self):
        """Record failed request"""
        self.error_count += 1


class CircuitBreaker:
    """Circuit breaker for host-level failures"""
    
    def __init__(self, failure_threshold: int = 10, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.blocked_hosts: Set[str] = set()
    
    def is_allowed(self, host: str) -> bool:
        """Check if requests to host are allowed"""
        if host not in self.blocked_hosts:
            return True
        
        # Check if recovery timeout has passed
        last_failure = self.last_failure_time.get(host, 0)
        if time.time() - last_failure > self.recovery_timeout:
            self.blocked_hosts.discard(host)
            self.failures.pop(host, None)
            self.last_failure_time.pop(host, None)
            logger.info("Circuit breaker recovered", host=host)
            return True
        
        return False
    
    def record_failure(self, host: str):
        """Record failure for host"""
        self.failures[host] = self.failures.get(host, 0) + 1
        self.last_failure_time[host] = time.time()
        
        if self.failures[host] >= self.failure_threshold:
            self.blocked_hosts.add(host)
            logger.warning("Circuit breaker tripped", host=host, 
                          failures=self.failures[host])
    
    def record_success(self, host: str):
        """Record success for host"""
        if host in self.failures:
            self.failures[host] = max(0, self.failures[host] - 1)


class StatsManager:
    """Manages real-time statistics"""
    
    def __init__(self, scan_id: str, crack_id: str):
        self.scan_id = scan_id
        self.crack_id = crack_id
        self.start_time = time.time()
        self.last_update = time.time()
        
        # Counters
        self.checks_count = 0
        self.urls_count = 0
        self.hits_count = 0
        self.errors_count = 0
        
        # Rates (per second)
        self.checks_per_sec = 0.0
        self.urls_per_sec = 0.0
        
        # Resource tracking
        self.process = psutil.Process()
        
    async def update_stats(self, checks: int = 0, urls: int = 0, hits: int = 0, errors: int = 0):
        """Update statistics and broadcast"""
        now = time.time()
        time_diff = now - self.last_update
        
        if time_diff >= 1.0:  # Update rates every second
            self.checks_per_sec = (self.checks_count - getattr(self, '_last_checks', 0)) / time_diff
            self.urls_per_sec = (self.urls_count - getattr(self, '_last_urls', 0)) / time_diff
            
            self._last_checks = self.checks_count
            self._last_urls = self.urls_count
            self.last_update = now
            
            # Broadcast stats via Redis pub/sub
            await self._broadcast_stats()
        
        self.checks_count += checks
        self.urls_count += urls
        self.hits_count += hits
        self.errors_count += errors
    
    async def _broadcast_stats(self):
        """Broadcast statistics via Redis pub/sub"""
        try:
            from .redis_manager import get_redis
            redis = get_redis()
            
            # Get resource usage
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            ram_mb = memory_info.rss / 1024 / 1024
            
            stats = {
                "scan_id": self.scan_id,
                "crack_id": self.crack_id,
                "checks_per_sec": self.checks_per_sec,
                "urls_per_sec": self.urls_per_sec,
                "total_checks": self.checks_count,
                "total_urls": self.urls_count,
                "total_hits": self.hits_count,
                "total_errors": self.errors_count,
                "cpu_percent": cpu_percent,
                "ram_mb": ram_mb,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await redis.publish(f"scan_stats:{self.scan_id}", stats)
            
        except Exception as e:
            logger.warning("Failed to broadcast stats", scan_id=self.scan_id, error=str(e))


class EnhancedScanner:
    """Enhanced scanner with high concurrency support"""
    
    def __init__(self):
        self.active_scans: Dict[str, ScanResult] = {}
        self.scan_tasks: Dict[str, asyncio.Task] = {}
        self.findings: Dict[str, List[Finding]] = {}
        self.stats_managers: Dict[str, StatsManager] = {}
        self.concurrency_managers: Dict[str, ConcurrencyManager] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # HTTP client with connection pooling
        self.http_client: Optional[httpx.AsyncClient] = None
        
    async def initialize(self):
        """Initialize the scanner"""
        # Create HTTP client with optimized settings
        limits = httpx.Limits(
            max_keepalive_connections=200,
            max_connections=500,
            keepalive_expiry=30
        )
        
        timeout = httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=5.0
        )
        
        self.http_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            verify=False,  # For scanning purposes
            follow_redirects=True
        )
        
        logger.info("Enhanced scanner initialized")
    
    async def close(self):
        """Close the scanner and cleanup resources"""
        # Cancel all active scans
        for task in self.scan_tasks.values():
            if not task.done():
                task.cancel()
                
        # Wait for tasks to complete
        if self.scan_tasks:
            await asyncio.gather(*self.scan_tasks.values(), return_exceptions=True)
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Enhanced scanner closed")
    
    def generate_crack_id(self) -> str:
        """Generate human-readable crack ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        random_part = str(uuid.uuid4().int)[:6]
        return f"{timestamp}{random_part}"
    
    async def start_scan(self, scan_request: ScanRequest) -> str:
        """Start a new scan and return scan ID"""
        scan_id = str(uuid.uuid4())
        crack_id = self.generate_crack_id()
        
        scan_result = ScanResult(
            id=scan_id,
            crack_id=crack_id,
            status=ScanStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            targets=scan_request.targets,
            config=scan_request
        )
        
        self.active_scans[scan_id] = scan_result
        self.findings[scan_id] = []
        
        # Initialize managers
        self.stats_managers[scan_id] = StatsManager(scan_id, crack_id)
        self.concurrency_managers[scan_id] = ConcurrencyManager(
            initial_concurrency=scan_request.concurrency,
            max_concurrency=min(scan_request.concurrency * 2, 50000)
        )
        self.circuit_breakers[scan_id] = CircuitBreaker()
        
        # Start scan task
        task = asyncio.create_task(self._run_scan(scan_id))
        self.scan_tasks[scan_id] = task
        
        # Store in database if available
        try:
            from .database import get_async_session, ScanDB
            session_factory = get_async_session()
            async with session_factory() as session:
                db_scan = ScanDB(
                    id=scan_id,
                    crack_id=crack_id,
                    status=ScanStatus.QUEUED.value,
                    targets=scan_request.targets,
                    wordlist=scan_request.wordlist,
                    modules=[m.value for m in scan_request.modules],
                    concurrency=scan_request.concurrency,
                    rate_limit=scan_request.rate_limit,
                    timeout=scan_request.timeout,
                    follow_redirects=scan_request.follow_redirects,
                    regex_rules=scan_request.regex_rules,
                    path_rules=scan_request.path_rules,
                    notes=scan_request.notes
                )
                session.add(db_scan)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to store scan in database", error=str(e))
        
        logger.info("Scan started", scan_id=scan_id, crack_id=crack_id, 
                   targets=len(scan_request.targets), concurrency=scan_request.concurrency)
        
        return scan_id
    
    async def _run_scan(self, scan_id: str):
        """Execute scan using httpx CLI executor"""
        try:
            scan_result = self.active_scans[scan_id]
            scan_result.status = ScanStatus.RUNNING
            scan_result.started_at = datetime.now(timezone.utc)
            
            # Broadcast scan started
            await self._broadcast_scan_event(scan_id, WSEventType.SCAN_STATUS, {
                "status": ScanStatus.RUNNING.value,
                "started_at": scan_result.started_at.isoformat()
            })
            
            # Initialize scan tracking
            if scan_id not in self.findings:
                self.findings[scan_id] = []
            
            # Check if httpx is available
            if not httpx_executor.is_httpx_available():
                error_msg = "httpx binary not found - please install httpx CLI tool"
                scan_result.status = ScanStatus.FAILED
                scan_result.error_message = error_msg
                scan_result.completed_at = datetime.now(timezone.utc)
                
                await self._broadcast_scan_event(scan_id, WSEventType.SCAN_LOG, {
                    "message": error_msg,
                    "level": "error"
                })
                return
            
            # Execute scan with httpx
            logger.info("Starting httpx scan execution", scan_id=scan_id, 
                       targets=len(scan_result.config.targets))
            
            success = await httpx_executor.execute_scan(
                scan_id,
                scan_result.config,
                progress_callback=self._on_scan_progress,
                log_callback=self._on_scan_log,
                hit_callback=self._on_scan_hit
            )
            
            # Mark scan as completed
            if success:
                scan_result.status = ScanStatus.COMPLETED
                scan_result.completed_at = datetime.now(timezone.utc)
                
                await self._broadcast_scan_event(scan_id, WSEventType.SCAN_STATUS, {
                    "status": ScanStatus.COMPLETED.value,
                    "completed_at": scan_result.completed_at.isoformat()
                })
                
                logger.info("Scan completed successfully", scan_id=scan_id, 
                           findings=len(self.findings.get(scan_id, [])))
            else:
                scan_result.status = ScanStatus.FAILED
                scan_result.error_message = "httpx execution failed"
                scan_result.completed_at = datetime.now(timezone.utc)
                
                logger.error("Scan failed", scan_id=scan_id)
            
        except asyncio.CancelledError:
            logger.info("Scan cancelled", scan_id=scan_id)
            scan_result.status = ScanStatus.STOPPED
            scan_result.stopped_at = datetime.now(timezone.utc)
            
            # Stop httpx process
            await httpx_executor.stop_scan(scan_id)
            
        except Exception as e:
            logger.error("Scan failed", scan_id=scan_id, error=str(e))
            scan_result.status = ScanStatus.FAILED
            scan_result.error_message = str(e)
            scan_result.completed_at = datetime.now(timezone.utc)
        finally:
            # Cleanup
            self.stats_managers.pop(scan_id, None)
            self.concurrency_managers.pop(scan_id, None) 
            self.circuit_breakers.pop(scan_id, None)
            self.scan_tasks.pop(scan_id, None)
    
    # Callback methods for httpx executor
    async def _on_scan_progress(self, scan_id: str, processed: int, total: int, 
                               checks_per_sec: float, urls_per_sec: float, eta_seconds: Optional[int]):
        """Handle scan progress updates from httpx executor"""
        scan_result = self.active_scans.get(scan_id)
        if not scan_result:
            return
            
        # Update scan result
        scan_result.processed_urls = processed
        scan_result.total_urls = total if total > 0 else processed
        scan_result.checks_per_sec = checks_per_sec
        scan_result.urls_per_sec = urls_per_sec
        scan_result.eta_seconds = eta_seconds
        scan_result.progress_percent = (processed / total * 100) if total > 0 else 0
        
        # Broadcast progress
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_PROGRESS, {
            "processed_urls": processed,
            "total_urls": total,
            "progress_percent": scan_result.progress_percent,
            "checks_per_sec": checks_per_sec,
            "urls_per_sec": urls_per_sec,
            "eta_seconds": eta_seconds
        })
    
    async def _on_scan_log(self, scan_id: str, message: str, level: str):
        """Handle log messages from httpx executor"""
        # Broadcast log message
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_LOG, {
            "message": message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def _on_scan_hit(self, scan_id: str, finding_data: Dict[str, Any]):
        """Handle scan hits from httpx executor"""
        try:
            # Create finding from httpx data
            finding_id = str(uuid.uuid4())
            scan_result = self.active_scans.get(scan_id)
            if not scan_result:
                return
                
            finding = Finding(
                id=finding_id,
                scan_id=scan_id,
                crack_id=scan_result.crack_id,
                service="web",
                pattern_id="httpx_hit",
                url=finding_data.get('url', ''),
                source_url=finding_data.get('url', ''),
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                evidence=f"Status: {finding_data.get('status_code', 0)}, "
                         f"Length: {finding_data.get('content_length', 0)}, "
                         f"Title: {finding_data.get('title', 'N/A')}",
                evidence_masked=f"HTTP {finding_data.get('status_code', 0)} response",
                confidence=0.6,
                severity="low",
                status_code=finding_data.get('status_code', 0),
                content_length=finding_data.get('content_length', 0),
                metadata=finding_data
            )
            
            # Store finding
            if scan_id not in self.findings:
                self.findings[scan_id] = []
            self.findings[scan_id].append(finding)
            
            # Update scan result counts
            scan_result.findings_count = len(self.findings[scan_id])
            scan_result.hits_count = scan_result.findings_count
            
            # Broadcast hit
            await self._broadcast_scan_event(scan_id, WSEventType.SCAN_HIT, {
                "finding_id": finding_id,
                "url": finding.url,
                "service": finding.service,
                "status_code": finding.status_code,
                "content_length": finding.content_length,
                "title": finding_data.get('title', ''),
                "timestamp": finding.first_seen.isoformat()
            })
            
        except Exception as e:
            logger.error("Error processing scan hit", scan_id=scan_id, error=str(e))
    
    async def _build_urls_enhanced(self, scan_result: ScanResult) -> List[str]:
        """Enhanced URL building with better performance"""
        urls = []
        config = config_manager.get_config()
        
        # Load wordlist
        wordlist_path = Path("data") / scan_result.config.wordlist
        if not wordlist_path.exists():
            await self._create_default_wordlist(wordlist_path)
        
        # Read paths from wordlist
        paths = []
        try:
            with open(wordlist_path, 'r') as f:
                paths = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error("Failed to read wordlist", path=str(wordlist_path), error=str(e))
            return []
        
        # Add custom path rules
        if scan_result.config.path_rules:
            paths.extend(scan_result.config.path_rules)
        
        # Build URLs from targets and paths
        for target in scan_result.targets:
            if not target.startswith(('http://', 'https://')):
                target = f"https://{target}"
            
            for path in paths:
                if not path.startswith('/'):
                    path = f"/{path}"
                url = f"{target.rstrip('/')}{path}"
                urls.append(url)
        
        logger.info("URLs built", scan_id=scan_result.id, 
                   targets=len(scan_result.targets), 
                   paths=len(paths), 
                   total_urls=len(urls))
        
        return urls
    
    async def _scan_urls_concurrent(self, scan_id: str, urls: List[str]):
        """High-concurrency URL scanning with backpressure"""
        scan_result = self.active_scans[scan_id]
        concurrency_mgr = self.concurrency_managers[scan_id]
        circuit_breaker = self.circuit_breakers[scan_id]
        stats_mgr = self.stats_managers[scan_id]
        
        # Create throttler for rate limiting
        throttler = Throttler(rate_limit=scan_result.config.rate_limit)
        
        # Process URLs in batches to manage memory
        batch_size = min(10000, len(urls))
        processed = 0
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size] 
            
            # Use adaptive concurrency
            current_concurrency = concurrency_mgr.current_concurrency
            
            # Create semaphore for batch processing
            semaphore = asyncio.Semaphore(current_concurrency)
            
            tasks = []
            for url in batch:
                # Check circuit breaker
                host = httpx.URL(url).host
                if not circuit_breaker.is_allowed(host):
                    continue
                
                task = asyncio.create_task(self._scan_single_url_with_semaphore(
                    scan_id, url, throttler, circuit_breaker, stats_mgr, semaphore
                ))
                tasks.append(task)
            
            # Wait for batch completion
            await asyncio.gather(*tasks, return_exceptions=True)
            
            processed += len(batch)
            scan_result.processed_urls = processed
            
            # Update progress
            progress = (processed / len(urls)) * 100
            scan_result.progress_percent = progress
            
            # Broadcast progress
            await self._broadcast_scan_event(scan_id, WSEventType.SCAN_PROGRESS, {
                "processed_urls": processed,
                "total_urls": len(urls),
                "progress_percent": round(progress, 1)
            })
            
            # Adjust concurrency based on performance
            concurrency_mgr.adjust_concurrency()
            
            logger.debug("Batch processed", scan_id=scan_id, 
                        processed=processed, total=len(urls),
                        concurrency=concurrency_mgr.current_concurrency)
    
    async def _scan_single_url_with_semaphore(self, scan_id: str, url: str, throttler: Throttler, 
                                            circuit_breaker: CircuitBreaker, stats_mgr: StatsManager,
                                            semaphore: asyncio.Semaphore):
        """Scan a single URL with semaphore control"""
        async with semaphore:
            await self._scan_single_url(scan_id, url, throttler, circuit_breaker, stats_mgr)
    
    async def _scan_single_url(self, scan_id: str, url: str, throttler: Throttler, 
                             circuit_breaker: CircuitBreaker, stats_mgr: StatsManager):
        """Scan a single URL for secrets"""
        try:
            # Apply rate limiting
            async with throttler:
                # Make HTTP request
                response = await self.http_client.get(
                    url,
                    timeout=self.active_scans[scan_id].config.timeout
                )
                
                # Update stats
                await stats_mgr.update_stats(checks=1)
                circuit_breaker.record_success(httpx.URL(url).host)
                
                # Process response for secrets
                if response.status_code == 200:
                    await self._process_response(scan_id, url, response.text)
                    await stats_mgr.update_stats(urls=1)
                
        except httpx.TimeoutException:
            circuit_breaker.record_failure(httpx.URL(url).host)
            await stats_mgr.update_stats(errors=1)
        except Exception as e:
            circuit_breaker.record_failure(httpx.URL(url).host)
            await stats_mgr.update_stats(errors=1)
            logger.debug("URL scan failed", url=url, error=str(e))
    
    async def _process_response(self, scan_id: str, url: str, content: str):
        """Process HTTP response for secrets using patterns"""
        scan_result = self.active_scans[scan_id]
        config = config_manager.get_config()
        
        # Get patterns based on selected modules
        patterns = []
        if scan_result.config.modules:
            for module in scan_result.config.modules:
                patterns.extend(self._get_patterns_for_module(module))
        else:
            patterns = config.default_patterns
        
        # Add custom regex patterns
        if scan_result.config.regex_rules:
            for regex in scan_result.config.regex_rules:
                patterns.append(SecretPattern(
                    name="Custom",
                    pattern=regex,
                    description="Custom regex pattern",
                    module_type=ModuleType.GENERIC
                ))
        
        # Search for patterns in content
        for pattern in patterns:
            try:
                matches = re.finditer(pattern.pattern, content, re.MULTILINE)
                for match in matches:
                    await self._create_finding_enhanced(scan_id, pattern, url, match.group())
            except re.error as e:
                logger.warning("Invalid regex pattern", pattern=pattern.pattern, error=str(e))
    
    async def _create_finding_enhanced(self, scan_id: str, pattern: SecretPattern, 
                                     url: str, evidence: str):
        """Create enhanced finding with validation"""
        finding_id = str(uuid.uuid4())
        crack_id = self.active_scans[scan_id].crack_id
        
        # Mask evidence
        evidence_masked = self._mask_evidence(evidence)
        
        # Create basic finding
        finding = Finding(
            id=finding_id,
            scan_id=scan_id,
            crack_id=crack_id,
            service=pattern.module_type.value,
            pattern_id=pattern.name,
            url=url,
            source_url=url,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            evidence=evidence,
            evidence_masked=evidence_masked,
            confidence=0.5,
            severity="medium"
        )
        
        # Validate finding if it's a supported service
        if pattern.module_type != ModuleType.GENERIC:
            validation_result = await self._validate_finding(pattern.module_type, evidence)
            if validation_result:
                finding.works = validation_result.works
                finding.confidence = validation_result.confidence
                finding.regions = validation_result.regions
                finding.capabilities = validation_result.capabilities
                finding.quotas = validation_result.quotas
                finding.verified_identities = validation_result.verified_identities
                
                # Adjust severity based on validation
                if validation_result.works:
                    finding.severity = "high" if validation_result.confidence > 0.8 else "medium"
        
        # Store finding
        self.findings[scan_id].append(finding)
        
        # Store in database if available
        try:
            from .database import get_async_session, FindingDB
            session_factory = get_async_session()
            async with session_factory() as session:
                db_finding = FindingDB(
                    id=finding_id,
                    scan_id=scan_id,
                    crack_id=crack_id,
                    service=finding.service,
                    pattern_id=finding.pattern_id,
                    url=finding.url,
                    source_url=finding.source_url,
                    evidence=finding.evidence,
                    evidence_masked=finding.evidence_masked,
                    works=finding.works,
                    confidence=finding.confidence,
                    severity=finding.severity,
                    regions=finding.regions,
                    capabilities=finding.capabilities,
                    quotas=finding.quotas,
                    verified_identities=finding.verified_identities
                )
                session.add(db_finding)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to store finding in database", error=str(e))
        
        # Update scan stats
        scan_result = self.active_scans[scan_id]
        scan_result.findings_count += 1
        scan_result.hits_count += 1
        
        # Broadcast finding
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_HIT, {
            "hit_id": finding_id,
            "service": finding.service,
            "masked": True,
            "summary": f"{finding.service} credentials found",
            "works": finding.works,
            "confidence": finding.confidence,
            "severity": finding.severity,
            "source_url": url,
            "regions": finding.regions,
            "capabilities": finding.capabilities,
            "created_at": finding.created_at.isoformat()
        })
        
        await self.stats_managers[scan_id].update_stats(hits=1)
        
        logger.info("Finding created", scan_id=scan_id, service=finding.service, 
                   works=finding.works, confidence=finding.confidence)
    
    async def _validate_finding(self, module_type: ModuleType, evidence: str) -> Optional[ValidationResult]:
        """Validate finding using service-specific validators"""
        try:
            if module_type == ModuleType.AWS:
                return await self._validate_aws_credentials(evidence)
            elif module_type == ModuleType.SENDGRID:
                return await self._validate_sendgrid_key(evidence)
            elif module_type == ModuleType.DOCKER:
                return await self._validate_docker_api(evidence)
            elif module_type == ModuleType.K8S:
                return await self._validate_k8s_api(evidence)
            # Add more validators as needed
            
        except Exception as e:
            logger.warning("Validation failed", module_type=module_type.value, error=str(e))
        
        return None
    
    async def _validate_aws_credentials(self, evidence: str) -> ValidationResult:
        """Validate AWS credentials"""
        # Extract access key from evidence
        access_key_match = re.search(r'AKIA[0-9A-Z]{16}', evidence)
        if not access_key_match:
            return ValidationResult(works=False, confidence=0.1)
        
        # TODO: Implement actual AWS STS validation
        # For now, return mock validation
        return ValidationResult(
            works=True,
            confidence=0.9,
            regions=["us-east-1"],
            capabilities=["STS", "S3"],
            quotas={"max_buckets": 100},
            verified_identities=["root"]
        )
    
    async def _validate_sendgrid_key(self, evidence: str) -> ValidationResult:
        """Validate SendGrid API key"""
        # TODO: Implement actual SendGrid API validation
        return ValidationResult(
            works=True,
            confidence=0.8,
            capabilities=["send_email", "manage_templates"]
        )
    
    async def _validate_docker_api(self, evidence: str) -> ValidationResult:
        """Validate Docker API access"""
        # TODO: Implement actual Docker API validation
        return ValidationResult(
            works=True,
            confidence=0.9,
            capabilities=["container_management"]
        )
    
    async def _validate_k8s_api(self, evidence: str) -> ValidationResult:
        """Validate Kubernetes API access"""
        # TODO: Implement actual K8s API validation
        return ValidationResult(
            works=True,
            confidence=0.9,
            capabilities=["pod_management"]
        )
    
    def _get_patterns_for_module(self, module_type: ModuleType) -> List[SecretPattern]:
        """Get regex patterns for specific module"""
        patterns = {
            ModuleType.AWS: [
                SecretPattern(
                    name="AWS Access Key",
                    pattern=r'AKIA[0-9A-Z]{16}',
                    description="AWS Access Key ID",
                    module_type=ModuleType.AWS
                ),
                SecretPattern(
                    name="AWS Secret Key",
                    pattern=r'[A-Za-z0-9/+=]{40}',
                    description="AWS Secret Access Key",
                    module_type=ModuleType.AWS
                )
            ],
            ModuleType.SENDGRID: [
                SecretPattern(
                    name="SendGrid API Key",
                    pattern=r'SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}',
                    description="SendGrid API Key",
                    module_type=ModuleType.SENDGRID
                )
            ],
            ModuleType.STRIPE: [
                SecretPattern(
                    name="Stripe Secret Key",
                    pattern=r'sk_live_[A-Za-z0-9]{24}',
                    description="Stripe Secret Key",
                    module_type=ModuleType.STRIPE
                )
            ],
            ModuleType.DOCKER: [
                SecretPattern(
                    name="Docker API",
                    pattern=r'tcp://[^/\s]+:2375',
                    description="Docker API Endpoint",
                    module_type=ModuleType.DOCKER
                )
            ],
            ModuleType.K8S: [
                SecretPattern(
                    name="Kubernetes API",
                    pattern=r'https?://[^/\s]+:6443',
                    description="Kubernetes API Endpoint",
                    module_type=ModuleType.K8S
                )
            ]
        }
        
        return patterns.get(module_type, [])
    
    def _mask_evidence(self, evidence: str) -> str:
        """Mask sensitive parts of evidence for display"""
        if len(evidence) <= 8:
            return "*" * len(evidence)
        
        visible_chars = 4
        masked_length = len(evidence) - (visible_chars * 2)
        return evidence[:visible_chars] + "*" * masked_length + evidence[-visible_chars:]
    
    async def _broadcast_scan_event(self, scan_id: str, event_type: WSEventType, data: Dict[str, Any]):
        """Broadcast scan event via Redis pub/sub"""
        try:
            from .redis_manager import get_redis
            redis = get_redis()
            message = {
                "type": event_type.value,
                "scan_id": scan_id,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await redis.publish(f"scan_events:{scan_id}", message)
        except Exception as e:
            logger.warning("Failed to broadcast event", scan_id=scan_id, 
                        event_type=event_type.value, error=str(e))
    
    async def _create_default_wordlist(self, wordlist_path: Path):
        """Create default wordlist based on common paths"""
        default_paths = [
            "/.env",
            "/.aws/credentials", 
            "/config/database.yml",
            "/wp-config.php",
            "/admin/config.php",
            "/config.json",
            "/secrets.json",
            "/credentials.json",
            "/.git/config",
            "/docker-compose.yml",
            "/kubernetes.yaml"
        ]
        
        wordlist_path.parent.mkdir(exist_ok=True)
        with open(wordlist_path, 'w') as f:
            for path in default_paths:
                f.write(f"{path}\n")
    
    # Control methods
    async def pause_scan(self, scan_id: str) -> bool:
        """Pause a running scan"""
        if scan_id not in self.active_scans:
            return False
        
        scan_result = self.active_scans[scan_id]
        if scan_result.status != ScanStatus.RUNNING:
            return False
        
        scan_result.status = ScanStatus.PAUSED
        scan_result.paused_at = datetime.now(timezone.utc)
        
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_STATUS, {
            "status": ScanStatus.PAUSED.value,
            "paused_at": scan_result.paused_at.isoformat()
        })
        
        return True
    
    async def resume_scan(self, scan_id: str) -> bool:
        """Resume a paused scan"""
        if scan_id not in self.active_scans:
            return False
        
        scan_result = self.active_scans[scan_id]
        if scan_result.status != ScanStatus.PAUSED:
            return False
        
        scan_result.status = ScanStatus.RUNNING
        scan_result.paused_at = None
        
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_STATUS, {
            "status": ScanStatus.RUNNING.value
        })
        
        return True
    
    async def stop_scan(self, scan_id: str) -> bool:
        """Stop a running or paused scan"""
        if scan_id not in self.active_scans:
            return False
        
        # Stop httpx process first
        await httpx_executor.stop_scan(scan_id)
        
        # Cancel the scan task
        if scan_id in self.scan_tasks:
            task = self.scan_tasks[scan_id]
            if not task.done():
                task.cancel()
        
        scan_result = self.active_scans[scan_id]
        scan_result.status = ScanStatus.STOPPED
        scan_result.stopped_at = datetime.now(timezone.utc)
        
        await self._broadcast_scan_event(scan_id, WSEventType.SCAN_STATUS, {
            "status": ScanStatus.STOPPED.value,
            "stopped_at": scan_result.stopped_at.isoformat()
        })
        
        logger.info("Scan stopped", scan_id=scan_id)
        return True
    
    # Query methods
    def get_scan_result(self, scan_id: str) -> Optional[ScanResult]:
        """Get scan result by ID"""
        return self.active_scans.get(scan_id)
    
    def get_scan_findings(self, scan_id: str) -> List[Finding]:
        """Get findings for a scan"""
        return self.findings.get(scan_id, [])
    
    def list_scans(self) -> List[ScanResult]:
        """List all scans"""
        return list(self.active_scans.values())


# Global enhanced scanner instance
enhanced_scanner = EnhancedScanner()