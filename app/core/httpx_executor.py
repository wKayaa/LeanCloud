"""HTTPx CLI executor for real-time scanning with telemetry"""

import asyncio
import json
import re
import time
import tempfile
import signal
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, timezone
import structlog

from .models import ScanRequest, ScanResult, ScanStatus, Finding
from .config import config_manager

logger = structlog.get_logger()


class HTTPxExecutor:
    """Async httpx CLI executor with live telemetry"""
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.httpx_path = self._find_httpx_binary()
        self.running_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.scan_stats: Dict[str, Dict[str, Any]] = {}
        
    def _find_httpx_binary(self) -> Optional[str]:
        """Find httpx binary in PATH or config"""
        import shutil
        
        # Check config first
        if hasattr(self.config, 'httpx_path') and self.config.httpx_path:
            if Path(self.config.httpx_path).exists():
                return self.config.httpx_path
        
        # Check PATH
        httpx_path = shutil.which('httpx')
        if httpx_path:
            return httpx_path
            
        logger.warning("httpx binary not found in PATH or config")
        return None
    
    def is_httpx_available(self) -> bool:
        """Check if httpx binary is available"""
        return self.httpx_path is not None
    
    async def build_httpx_command(self, scan_request: ScanRequest, targets_file: str) -> List[str]:
        """Build httpx command from scan request"""
        if not self.httpx_path:
            raise RuntimeError("httpx binary not available")
            
        cmd = [
            self.httpx_path,
            "-l", targets_file,  # Input file with URLs
            "-json",             # JSON output for parsing
            "-silent",           # Reduce noise
            "-no-color",         # Plain output
        ]
        
        # Add scan-specific options
        if scan_request.timeout:
            cmd.extend(["-timeout", str(scan_request.timeout)])
            
        if not scan_request.follow_redirects:
            cmd.append("-no-follow-redirects")
            
        if scan_request.rate_limit:
            cmd.extend(["-rl", str(scan_request.rate_limit)])
            
        # Add concurrency (httpx uses -threads)
        if scan_request.concurrency:
            cmd.extend(["-threads", str(min(scan_request.concurrency, 1000))])
            
        # Add custom headers if needed
        cmd.extend(["-H", "User-Agent: HTTPx-Cloud-Scanner/1.0"])
        
        return cmd
    
    async def prepare_targets_file(self, scan_request: ScanRequest) -> str:
        """Prepare targets file for httpx"""
        # Create temporary file for targets
        fd, targets_file = tempfile.mkstemp(suffix='.txt', prefix='httpx_targets_')
        
        try:
            with open(targets_file, 'w') as f:
                # Build URLs from targets and wordlist
                urls = await self._build_target_urls(scan_request)
                for url in urls:
                    f.write(f"{url}\n")
            
            logger.info("Created targets file", 
                       file=targets_file, 
                       url_count=len(urls),
                       scan_id=getattr(scan_request, 'scan_id', 'unknown'))
            
            return targets_file
            
        except Exception as e:
            # Clean up on error
            try:
                Path(targets_file).unlink(missing_ok=True)
            except:
                pass
            raise e
            
    async def _build_target_urls(self, scan_request: ScanRequest) -> List[str]:
        """Build target URLs from targets and wordlist"""
        urls = []
        
        # Load wordlist paths
        wordlist_paths = []
        if scan_request.wordlist:
            wordlist_file = Path("data") / "lists" / scan_request.wordlist
            if wordlist_file.exists():
                try:
                    with open(wordlist_file, 'r') as f:
                        wordlist_paths = [line.strip() for line in f if line.strip()]
                except Exception as e:
                    logger.warning("Failed to load wordlist", 
                                 wordlist=scan_request.wordlist, error=str(e))
        
        # Default paths if no wordlist
        if not wordlist_paths:
            wordlist_paths = ['.well-known/security.txt', 'robots.txt', '.env', 'config.json']
        
        # Build URLs
        for target in scan_request.targets:
            target = target.strip()
            if not target:
                continue
                
            # Ensure target has protocol
            if not target.startswith(('http://', 'https://')):
                target = f"https://{target}"
            
            # Remove trailing slash
            target = target.rstrip('/')
            
            # Add paths
            for path in wordlist_paths:
                path = path.lstrip('/')
                urls.append(f"{target}/{path}")
        
        return urls
    
    async def execute_scan(self, scan_id: str, scan_request: ScanRequest, 
                          progress_callback=None, log_callback=None, hit_callback=None) -> bool:
        """Execute httpx scan with real-time telemetry"""
        
        if not self.is_httpx_available():
            if log_callback:
                await log_callback(scan_id, "httpx binary not available", "error")
            return False
        
        targets_file = None
        try:
            # Prepare targets file
            targets_file = await self.prepare_targets_file(scan_request)
            
            # Build command
            cmd = await self.build_httpx_command(scan_request, targets_file)
            
            if log_callback:
                await log_callback(scan_id, f"Starting httpx: {' '.join(cmd)}", "info")
            
            # Start process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=None  # Linux only
            )
            
            # Store process reference
            self.running_processes[scan_id] = process
            self.scan_stats[scan_id] = {
                'start_time': time.time(),
                'processed_urls': 0,
                'hits': 0,
                'errors': 0,
                'last_update': time.time()
            }
            
            # Monitor process output
            success = await self._monitor_process(
                scan_id, process, progress_callback, log_callback, hit_callback
            )
            
            return success
            
        except Exception as e:
            logger.error("Scan execution failed", scan_id=scan_id, error=str(e))
            if log_callback:
                await log_callback(scan_id, f"Execution failed: {str(e)}", "error")
            return False
            
        finally:
            # Cleanup
            self.running_processes.pop(scan_id, None)
            self.scan_stats.pop(scan_id, None)
            
            if targets_file:
                try:
                    Path(targets_file).unlink(missing_ok=True)
                except:
                    pass
    
    async def _monitor_process(self, scan_id: str, process: asyncio.subprocess.Process,
                              progress_callback=None, log_callback=None, hit_callback=None) -> bool:
        """Monitor process output and emit telemetry"""
        
        stats = self.scan_stats[scan_id]
        
        async def read_stdout():
            """Read and parse stdout"""
            while True:
                try:
                    line = await process.stdout.readline()
                    if not line:
                        break
                        
                    line = line.decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    # Try to parse as JSON (httpx -json output)
                    try:
                        data = json.loads(line)
                        await self._process_json_output(scan_id, data, stats, 
                                                       progress_callback, hit_callback)
                    except json.JSONDecodeError:
                        # Regular text line
                        if log_callback:
                            await log_callback(scan_id, line, "info")
                            
                except Exception as e:
                    logger.error("Error reading stdout", scan_id=scan_id, error=str(e))
                    break
        
        async def read_stderr():
            """Read stderr for errors"""
            while True:
                try:
                    line = await process.stderr.readline()
                    if not line:
                        break
                        
                    line = line.decode('utf-8', errors='ignore').strip()
                    if line and log_callback:
                        await log_callback(scan_id, line, "error")
                        stats['errors'] += 1
                        
                except Exception as e:
                    logger.error("Error reading stderr", scan_id=scan_id, error=str(e))
                    break
        
        # Start reading tasks
        stdout_task = asyncio.create_task(read_stdout())
        stderr_task = asyncio.create_task(read_stderr())
        
        # Wait for process completion
        try:
            return_code = await process.wait()
            
            # Wait for output tasks to complete
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            
            success = return_code == 0
            if log_callback:
                if success:
                    await log_callback(scan_id, f"httpx completed successfully", "info")
                else:
                    await log_callback(scan_id, f"httpx exited with code {return_code}", "error")
            
            return success
            
        except asyncio.CancelledError:
            # Process was cancelled/stopped
            if log_callback:
                await log_callback(scan_id, "Scan stopped by user", "info")
            
            # Try to terminate gracefully
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            
            return False
    
    async def _process_json_output(self, scan_id: str, data: Dict[str, Any], stats: Dict[str, Any],
                                  progress_callback=None, hit_callback=None):
        """Process JSON output from httpx"""
        
        try:
            # Update stats
            stats['processed_urls'] += 1
            stats['last_update'] = time.time()
            
            # Check for interesting responses
            status_code = data.get('status_code', 0)
            url = data.get('url', '')
            content_length = data.get('content_length', 0)
            
            # Simple hit detection (customize based on needs)
            is_hit = False
            if status_code == 200 and content_length > 0:
                # Check for interesting content indicators
                body = data.get('body', '')
                if any(keyword in body.lower() for keyword in [
                    'api', 'key', 'secret', 'token', 'password', 'config'
                ]):
                    is_hit = True
            
            if is_hit:
                stats['hits'] += 1
                
                if hit_callback:
                    finding_data = {
                        'url': url,
                        'status_code': status_code,
                        'content_length': content_length,
                        'title': data.get('title', ''),
                        'server': data.get('server', ''),
                        'content_type': data.get('content_type', ''),
                        'found_at': datetime.now(timezone.utc).isoformat()
                    }
                    await hit_callback(scan_id, finding_data)
            
            # Send progress update
            if progress_callback:
                # Calculate rates
                elapsed = time.time() - stats['start_time']
                urls_per_sec = stats['processed_urls'] / elapsed if elapsed > 0 else 0
                
                await progress_callback(
                    scan_id,
                    stats['processed_urls'],
                    0,  # total_urls unknown with httpx streaming
                    urls_per_sec,
                    urls_per_sec,
                    None  # eta unknown
                )
            
        except Exception as e:
            logger.error("Error processing JSON output", scan_id=scan_id, error=str(e))
    
    async def stop_scan(self, scan_id: str) -> bool:
        """Stop a running scan"""
        process = self.running_processes.get(scan_id)
        if not process:
            return False
        
        try:
            # Send SIGTERM first
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if needed
                process.kill()
                await process.wait()
            
            logger.info("Scan stopped", scan_id=scan_id)
            return True
            
        except Exception as e:
            logger.error("Error stopping scan", scan_id=scan_id, error=str(e))
            return False
    
    def get_scan_stats(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get current scan statistics"""
        return self.scan_stats.get(scan_id)
    
    def list_running_scans(self) -> List[str]:
        """List currently running scan IDs"""
        return list(self.running_processes.keys())


# Global executor instance
httpx_executor = HTTPxExecutor()