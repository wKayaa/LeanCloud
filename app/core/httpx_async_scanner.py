"""
HTTPx Async Scanner - Real async scanning with httpx.AsyncClient
This replaces the CLI-based httpx_executor with native async implementation
"""

import asyncio
import httpx
import time
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Callable
from pathlib import Path
from urllib.parse import urljoin, urlparse
import structlog

from .models import ScanRequest, ScanResult, ScanStatus, Finding, WSEventType
from .redis_manager import get_redis
from .settings import get_settings

logger = structlog.get_logger()


class HTTPxAsyncScanner:
    """High-performance async scanner using httpx.AsyncClient"""
    
    def __init__(self):
        self.active_scans: Dict[str, ScanResult] = {}
        self.scan_tasks: Dict[str, asyncio.Task] = {}
        self.findings: Dict[str, List[Finding]] = {}
        self.clients: Dict[str, httpx.AsyncClient] = {}
        
    async def initialize(self):
        """Initialize the scanner"""
        logger.info("HTTPx Async Scanner initialized")
        
    async def create_scan(self, request: ScanRequest) -> str:
        """Create a new scan and return scan ID"""
        scan_id = str(uuid.uuid4())
        crack_id = f"scan_{int(time.time())}"
        
        # Create scan result
        scan_result = ScanResult(
            id=scan_id,
            crack_id=crack_id,
            status=ScanStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            targets=request.targets,
            config=request
        )
        
        self.active_scans[scan_id] = scan_result
        self.findings[scan_id] = []
        
        logger.info("Scan created", scan_id=scan_id, targets=len(request.targets))
        return scan_id
    
    async def start_scan(self, scan_id: str):
        """Start a scan asynchronously"""
        if scan_id not in self.active_scans:
            raise ValueError(f"Scan {scan_id} not found")
        
        scan_result = self.active_scans[scan_id]
        if scan_result.status != ScanStatus.QUEUED:
            raise ValueError(f"Scan {scan_id} is not in queued state")
        
        # Start scan task
        task = asyncio.create_task(self._run_scan(scan_id))
        self.scan_tasks[scan_id] = task
        
        logger.info("Scan started", scan_id=scan_id)
        return task
    
    async def _run_scan(self, scan_id: str):
        """Execute the actual scan"""
        scan_result = self.active_scans[scan_id]
        
        try:
            scan_result.status = ScanStatus.RUNNING
            scan_result.started_at = datetime.now(timezone.utc)
            
            # Broadcast scan started
            await self._broadcast_event(scan_id, WSEventType.SCAN_STATUS, {
                "status": ScanStatus.RUNNING.value,
                "started_at": scan_result.started_at.isoformat()
            })
            
            # Create HTTP client for this scan
            client = await self._create_http_client(scan_result.config)
            self.clients[scan_id] = client
            
            # Generate URLs to scan
            urls_to_scan = await self._generate_urls(scan_result.config)
            scan_result.total_urls = len(urls_to_scan)
            
            # Run scan with concurrency control
            await self._scan_urls(scan_id, urls_to_scan)
            
            # Mark as completed
            scan_result.status = ScanStatus.COMPLETED
            scan_result.completed_at = datetime.now(timezone.utc)
            scan_result.progress_percent = 100.0
            
            await self._broadcast_event(scan_id, WSEventType.SCAN_STATUS, {
                "status": ScanStatus.COMPLETED.value,
                "completed_at": scan_result.completed_at.isoformat(),
                "findings_count": scan_result.findings_count
            })
            
            logger.info("Scan completed", scan_id=scan_id, findings=scan_result.findings_count)
            
        except Exception as e:
            scan_result.status = ScanStatus.FAILED
            scan_result.error_message = str(e)
            scan_result.completed_at = datetime.now(timezone.utc)
            
            await self._broadcast_event(scan_id, WSEventType.SCAN_STATUS, {
                "status": ScanStatus.FAILED.value,
                "error_message": str(e)
            })
            
            logger.error("Scan failed", scan_id=scan_id, error=str(e))
            
        finally:
            # Cleanup client
            if scan_id in self.clients:
                await self.clients[scan_id].aclose()
                del self.clients[scan_id]
    
    async def _create_http_client(self, config: ScanRequest) -> httpx.AsyncClient:
        """Create configured HTTP client"""
        return httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            follow_redirects=config.follow_redirects,
            limits=httpx.Limits(
                max_connections=min(config.concurrency, 100),
                max_keepalive_connections=20
            ),
            headers={
                'User-Agent': 'LeanCloud-Scanner/1.0 (Security Testing)'
            }
        )
    
    async def _generate_urls(self, config: ScanRequest) -> List[str]:
        """Generate URLs to scan based on targets and wordlist"""
        urls = []
        
        # Load paths from wordlist file
        wordlist_path = Path("data") / config.wordlist
        if not wordlist_path.exists():
            wordlist_path = Path("data/paths.txt")  # fallback
        
        paths = []
        if wordlist_path.exists():
            with open(wordlist_path, 'r') as f:
                paths = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        else:
            # Default paths if no wordlist
            paths = ['robots.txt', '.env', 'config.json', 'admin/', 'api/']
        
        # Generate URLs for each target
        for target in config.targets:
            if not target.startswith(('http://', 'https://')):
                target = f"http://{target}"
            
            for path in paths:
                url = urljoin(target, path)
                urls.append(url)
        
        return urls
    
    async def _scan_urls(self, scan_id: str, urls: List[str]):
        """Scan URLs with concurrency control"""
        scan_result = self.active_scans[scan_id]
        client = self.clients[scan_id]
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(scan_result.config.concurrency)
        
        # Create tasks for all URLs
        tasks = []
        for url in urls:
            task = asyncio.create_task(self._scan_single_url(scan_id, url, client, semaphore))
            tasks.append(task)
        
        # Process URLs in batches to avoid overwhelming the system
        batch_size = 1000
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            
            # Update progress
            scan_result.processed_urls = i + len(batch)
            scan_result.progress_percent = (scan_result.processed_urls / scan_result.total_urls) * 100
            
            # Broadcast progress
            await self._broadcast_event(scan_id, WSEventType.SCAN_PROGRESS, {
                "processed_urls": scan_result.processed_urls,
                "total_urls": scan_result.total_urls,
                "progress_percent": scan_result.progress_percent
            })
    
    async def _scan_single_url(self, scan_id: str, url: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
        """Scan a single URL"""
        async with semaphore:
            scan_result = self.active_scans[scan_id]
            
            try:
                response = await client.get(url)
                
                # Check for findings
                findings = await self._analyze_response(scan_id, url, response)
                if findings:
                    self.findings[scan_id].extend(findings)
                    scan_result.findings_count += len(findings)
                    scan_result.hits_count += len([f for f in findings if f.works])
                    
                    # Broadcast findings
                    for finding in findings:
                        await self._broadcast_event(scan_id, WSEventType.SCAN_HIT, {
                            "url": finding.url,
                            "service": finding.service,
                            "evidence": finding.evidence_masked,
                            "confidence": finding.confidence
                        })
                
            except Exception as e:
                scan_result.errors_count += 1
                logger.debug("URL scan failed", url=url, error=str(e))
    
    async def _analyze_response(self, scan_id: str, url: str, response: httpx.Response) -> List[Finding]:
        """Analyze HTTP response for findings"""
        findings = []
        scan_result = self.active_scans[scan_id]
        
        # Only analyze successful responses or specific error codes
        if response.status_code not in [200, 403, 401, 500]:
            return findings
        
        # Get response content
        try:
            content = response.text
        except:
            return findings
        
        # Load patterns from config
        patterns = self._get_secret_patterns()
        
        # Search for secrets in response
        for pattern in patterns:
            matches = re.finditer(pattern['pattern'], content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                finding = Finding(
                    id=uuid.uuid4(),
                    scan_id=scan_result.id,
                    crack_id=scan_result.crack_id,
                    service=pattern.get('service', 'generic'),
                    pattern_id=pattern['name'],
                    url=url,
                    source_url=url,
                    evidence=match.group(0),
                    evidence_masked=self._mask_sensitive_data(match.group(0)),
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                    confidence=pattern.get('confidence', 0.7),
                    severity=pattern.get('severity', 'medium')
                )
                findings.append(finding)
        
        return findings
    
    def _get_secret_patterns(self) -> List[Dict[str, Any]]:
        """Get secret detection patterns"""
        return [
            {
                'name': 'AWS Access Key',
                'pattern': r'AKIA[A-Z0-9]{16}',
                'service': 'aws',
                'confidence': 0.9,
                'severity': 'high'
            },
            {
                'name': 'SendGrid API Key',
                'pattern': r'SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}',
                'service': 'sendgrid',
                'confidence': 0.95,
                'severity': 'high'
            },
            {
                'name': 'Generic API Key',
                'pattern': r'api[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_\-]{20,})',
                'service': 'generic',
                'confidence': 0.6,
                'severity': 'medium'
            },
            {
                'name': 'Private Key',
                'pattern': r'-----BEGIN[A-Z\s]+PRIVATE KEY-----',
                'service': 'crypto',
                'confidence': 0.9,
                'severity': 'critical'
            }
        ]
    
    def _mask_sensitive_data(self, data: str) -> str:
        """Mask sensitive parts of evidence"""
        if len(data) <= 8:
            return '*' * len(data)
        
        # Show first 4 and last 4 characters
        return data[:4] + '*' * (len(data) - 8) + data[-4:]
    
    async def _broadcast_event(self, scan_id: str, event_type: WSEventType, data: Dict[str, Any]):
        """Broadcast event via Redis pub/sub or fallback storage"""
        event = {
            "type": event_type.value,
            "scan_id": scan_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            redis = get_redis()
            channel = f"scan_events:{scan_id}"
            await redis.publish(channel, event)
        except Exception as e:
            logger.debug("Failed to broadcast event", scan_id=scan_id, error=str(e))
            # TODO: Store event for polling fallback
    
    async def stop_scan(self, scan_id: str):
        """Stop a running scan"""
        if scan_id in self.scan_tasks:
            task = self.scan_tasks[scan_id]
            task.cancel()
            
            scan_result = self.active_scans.get(scan_id)
            if scan_result:
                scan_result.status = ScanStatus.STOPPED
                scan_result.stopped_at = datetime.now(timezone.utc)
        
        # Cleanup
        if scan_id in self.clients:
            await self.clients[scan_id].aclose()
            del self.clients[scan_id]
        
        logger.info("Scan stopped", scan_id=scan_id)
    
    def get_scan_result(self, scan_id: str) -> Optional[ScanResult]:
        """Get scan result"""
        return self.active_scans.get(scan_id)
    
    def get_scan_findings(self, scan_id: str) -> List[Finding]:
        """Get scan findings"""
        return self.findings.get(scan_id, [])


# Global scanner instance
httpx_async_scanner = HTTPxAsyncScanner()