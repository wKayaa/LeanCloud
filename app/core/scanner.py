import asyncio
import subprocess
import tempfile
import re
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncGenerator
from .models import ScanRequest, ScanResult, ScanStatus, Finding, SecretPattern
from .config import config_manager
import logging

logger = logging.getLogger(__name__)


class Scanner:
    def __init__(self):
        self.active_scans: Dict[str, ScanResult] = {}
        self.scan_processes: Dict[str, subprocess.Popen] = {}
        self.findings: Dict[str, List[Finding]] = {}
    
    async def start_scan(self, scan_request: ScanRequest) -> str:
        """Start a new scan and return scan ID"""
        scan_id = str(uuid.uuid4())
        
        scan_result = ScanResult(
            id=scan_id,
            status=ScanStatus.QUEUED,
            created_at=datetime.now(),
            targets=scan_request.targets,
            config=scan_request
        )
        
        self.active_scans[scan_id] = scan_result
        self.findings[scan_id] = []
        
        # Start scan in background
        asyncio.create_task(self._run_scan(scan_id))
        
        return scan_id
    
    async def _run_scan(self, scan_id: str):
        """Execute the two-pass scan process"""
        scan_result = self.active_scans[scan_id]
        
        try:
            scan_result.status = ScanStatus.RUNNING
            scan_result.started_at = datetime.now()
            
            # Pass 1: Build URLs from paths
            urls = await self._build_urls(scan_result)
            scan_result.total_urls = len(urls)
            
            # Pass 2: Scan responses for secrets
            await self._scan_for_secrets(scan_id, urls)
            
            scan_result.status = ScanStatus.COMPLETED
            scan_result.completed_at = datetime.now()
            scan_result.findings_count = len(self.findings[scan_id])
            
        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {str(e)}")
            scan_result.status = ScanStatus.FAILED
            scan_result.error_message = str(e)
            scan_result.completed_at = datetime.now()
    
    async def _build_urls(self, scan_result: ScanResult) -> List[str]:
        """Pass 1: Build URLs from targets and wordlist"""
        urls = []
        wordlist_path = Path(f"data/{scan_result.config.wordlist}")
        
        if not wordlist_path.exists():
            # Create default paths.txt if it doesn't exist
            await self._create_default_wordlist(wordlist_path)
        
        paths = []
        with open(wordlist_path, 'r') as f:
            paths = [line.strip() for line in f if line.strip()]
        
        for target in scan_result.targets:
            # Normalize target URL
            if not target.startswith(('http://', 'https://')):
                target = f"https://{target}"
            
            base_url = target.rstrip('/')
            
            for path in paths:
                path = path.lstrip('/')
                url = f"{base_url}/{path}"
                urls.append(url)
        
        return urls
    
    async def _create_default_wordlist(self, wordlist_path: Path):
        """Create default wordlist based on existing v5.sh patterns"""
        default_paths = [
            "robots.txt",
            ".env",
            ".git/config",
            "config.json",
            "settings.py",
            "database.yml",
            "wp-config.php",
            ".aws/credentials",
            ".ssh/id_rsa",
            "backup.sql",
            "dump.sql",
            "admin/config.php",
            "api/config.json",
            "config/database.yml",
            "js/config.js",
            ".vscode/settings.json",
            ".DS_Store",
            "package.json",
            "composer.json",
            "Gemfile",
            "requirements.txt",
            ".bak",
            ".old",
            ".backup",
            "test.php",
            "debug.log",
            "error.log",
            "access.log"
        ]
        
        wordlist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(wordlist_path, 'w') as f:
            for path in default_paths:
                f.write(f"{path}\n")
    
    async def _scan_for_secrets(self, scan_id: str, urls: List[str]):
        """Pass 2: Scan HTTP responses for secrets using httpx"""
        config = config_manager.get_config()
        scan_result = self.active_scans[scan_id]
        
        # Create temporary file with URLs
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for url in urls:
                f.write(f"{url}\n")
            urls_file = f.name
        
        try:
            processed = 0
            # Scan with each regex pattern
            for pattern in config.default_patterns:
                await self._scan_with_pattern(scan_id, urls_file, pattern)
                processed += len(urls)
                scan_result.processed_urls = min(processed, scan_result.total_urls)
        
        finally:
            # Cleanup temp file
            Path(urls_file).unlink(missing_ok=True)
    
    async def _scan_with_pattern(self, scan_id: str, urls_file: str, pattern: SecretPattern):
        """Scan URLs with a specific regex pattern using httpx"""
        config = config_manager.get_config()
        scan_config = self.active_scans[scan_id].config
        
        # Build httpx command
        cmd = [
            config.httpx_path,
            "-silent",
            "-l", urls_file,
            "-t", str(scan_config.concurrency),
            "-timeout", str(scan_config.timeout),
            "-mr", pattern.pattern
        ]
        
        if not scan_config.follow_redirects:
            cmd.append("-no-redirect")
        
        try:
            # Execute httpx command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                # Parse httpx output and create findings
                matches = stdout.decode().strip().split('\n')
                for match in matches:
                    if match.strip():
                        await self._create_finding(scan_id, pattern, match.strip())
                        
        except Exception as e:
            logger.error(f"Error scanning with pattern {pattern.name}: {str(e)}")
    
    async def _create_finding(self, scan_id: str, pattern: SecretPattern, url: str):
        """Create a finding from a matched URL"""
        # Extract the actual secret from the response
        try:
            # Get the response content to extract the secret
            cmd = [
                config_manager.get_config().httpx_path,
                "-silent",
                "-body",
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                response_body = stdout.decode()
                matches = re.findall(pattern.pattern, response_body)
                
                for match in matches:
                    # Create finding
                    finding = Finding(
                        id=str(uuid.uuid4()),
                        scan_id=scan_id,
                        provider=pattern.name,
                        pattern_id=pattern.name.lower().replace(' ', '_'),
                        url=url,
                        first_seen=datetime.now(),
                        last_seen=datetime.now(),
                        evidence=match if isinstance(match, str) else str(match),
                        evidence_masked=self._mask_evidence(match if isinstance(match, str) else str(match))
                    )
                    
                    self.findings[scan_id].append(finding)
                    
        except Exception as e:
            logger.error(f"Error creating finding for {url}: {str(e)}")
    
    def _mask_evidence(self, evidence: str) -> str:
        """Mask sensitive parts of evidence for display"""
        if len(evidence) <= 8:
            return "*" * len(evidence)
        
        visible_chars = 4
        masked_length = len(evidence) - (visible_chars * 2)
        return evidence[:visible_chars] + "*" * masked_length + evidence[-visible_chars:]
    
    def get_scan_result(self, scan_id: str) -> Optional[ScanResult]:
        """Get scan result by ID"""
        return self.active_scans.get(scan_id)
    
    def get_scan_findings(self, scan_id: str) -> List[Finding]:
        """Get findings for a scan"""
        return self.findings.get(scan_id, [])
    
    def list_scans(self) -> List[ScanResult]:
        """List all scans"""
        return list(self.active_scans.values())
    
    def stop_scan(self, scan_id: str) -> bool:
        """Stop a running scan"""
        if scan_id in self.scan_processes:
            process = self.scan_processes[scan_id]
            process.terminate()
            del self.scan_processes[scan_id]
            
            if scan_id in self.active_scans:
                self.active_scans[scan_id].status = ScanStatus.STOPPED
                self.active_scans[scan_id].completed_at = datetime.now()
            
            return True
        return False
    
    async def get_scan_logs(self, scan_id: str) -> AsyncGenerator[str, None]:
        """Stream scan logs (placeholder for real implementation)"""
        # This is a simplified implementation
        # In a real implementation, you'd stream actual logs from the scan process
        logs = [
            f"[{datetime.now().isoformat()}] Starting scan {scan_id}",
            f"[{datetime.now().isoformat()}] Building URL list...",
            f"[{datetime.now().isoformat()}] Starting pattern matching...",
        ]
        
        for log in logs:
            yield log
            await asyncio.sleep(0.1)


# Global scanner instance
scanner = Scanner()