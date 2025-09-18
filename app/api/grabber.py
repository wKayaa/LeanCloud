"""
Grabber API endpoints for domain list generation
Implements simple, safe domain processing worker
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
import structlog

from ..core.auth import get_current_user
from ..core.models import GrabberStatus, ListInfo

logger = structlog.get_logger()

router = APIRouter()

# Global grabber state
_grabber_status = GrabberStatus()
_grabber_task: Optional[asyncio.Task] = None


class SimpleGrabber:
    """
    Simple, safe domain grabber that performs basic permutations
    and normalization without intrusive actions
    """
    
    def __init__(self):
        self.data_dir = Path("data/lists")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    async def process_domains(self, base_domains: List[str]) -> List[str]:
        """
        Generate domain candidates through safe permutations
        """
        candidates = set()
        
        for domain in base_domains:
            # Basic normalization
            domain = domain.strip().lower()
            if not domain:
                continue
                
            candidates.add(domain)
            
            # Add common subdomains (safe, passive approach)
            common_subs = [
                'www', 'api', 'app', 'portal', 'admin', 'dev', 'test', 'staging',
                'mail', 'smtp', 'webmail', 'secure', 'support', 'help', 'docs',
                'cdn', 'static', 'assets', 'media', 'images', 'files'
            ]
            
            for sub in common_subs:
                candidates.add(f"{sub}.{domain}")
            
            # Add common TLD variations for base domain
            if '.' in domain:
                base_name = domain.split('.')[0]
                common_tlds = ['com', 'net', 'org', 'io', 'co', 'app']
                for tld in common_tlds:
                    candidates.add(f"{base_name}.{tld}")
        
        return list(candidates)
    
    async def save_candidates(self, candidates: List[str], filename: str) -> str:
        """Save generated candidates to a file"""
        filepath = self.data_dir / filename
        
        with open(filepath, 'w') as f:
            for candidate in sorted(candidates):
                f.write(f"{candidate}\n")
        
        return str(filepath)


grabber = SimpleGrabber()


async def _run_grabber_task(base_domains: List[str]):
    """Background task for running the grabber"""
    global _grabber_status
    
    try:
        _grabber_status.active = True
        _grabber_status.started_at = datetime.now(timezone.utc)
        _grabber_status.current_operation = "Processing domains"
        _grabber_status.processed_domains = 0
        _grabber_status.generated_candidates = 0
        
        logger.info("Grabber started", domain_count=len(base_domains))
        
        # Process domains in batches
        batch_size = 100
        all_candidates = []
        
        for i in range(0, len(base_domains), batch_size):
            batch = base_domains[i:i + batch_size]
            
            _grabber_status.current_operation = f"Processing batch {i//batch_size + 1}"
            _grabber_status.processed_domains = min(i + batch_size, len(base_domains))
            
            # Process batch
            batch_candidates = await grabber.process_domains(batch)
            all_candidates.extend(batch_candidates)
            
            # Small delay to prevent overwhelming
            await asyncio.sleep(0.1)
        
        # Remove duplicates
        unique_candidates = list(set(all_candidates))
        _grabber_status.generated_candidates = len(unique_candidates)
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"grabber_output_{timestamp}.txt"
        
        _grabber_status.current_operation = "Saving results"
        filepath = await grabber.save_candidates(unique_candidates, filename)
        
        _grabber_status.current_operation = "Completed"
        _grabber_status.estimated_completion = datetime.now(timezone.utc)
        
        logger.info("Grabber completed", 
                   input_domains=len(base_domains),
                   output_candidates=len(unique_candidates),
                   output_file=filepath)
        
    except Exception as e:
        logger.error("Grabber task failed", error=str(e))
        _grabber_status.current_operation = f"Error: {str(e)}"
    finally:
        _grabber_status.active = False


@router.post("/grabber/start")
async def start_grabber(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Start the domain grabber with existing domain lists"""
    global _grabber_task
    
    try:
        if _grabber_status.active:
            raise HTTPException(status_code=409, detail="Grabber is already running")
        
        # Look for existing domain files
        domain_files = []
        for pattern in ["*.txt", "*.list"]:
            domain_files.extend(grabber.data_dir.glob(pattern))
        
        if not domain_files:
            raise HTTPException(status_code=400, detail="No domain files found to process")
        
        # Read domains from files
        base_domains = []
        for domain_file in domain_files:
            try:
                with open(domain_file, 'r') as f:
                    domains = [line.strip() for line in f if line.strip()]
                    base_domains.extend(domains)
            except Exception as e:
                logger.warning("Failed to read domain file", file=str(domain_file), error=str(e))
        
        if not base_domains:
            raise HTTPException(status_code=400, detail="No valid domains found in files")
        
        # Remove duplicates
        base_domains = list(set(base_domains))
        
        # Start background task
        _grabber_task = asyncio.create_task(_run_grabber_task(base_domains))
        background_tasks.add_task(lambda: _grabber_task)
        
        return {
            "message": "Grabber started successfully",
            "input_domains": len(base_domains),
            "status": _grabber_status.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to start grabber", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grabber/status")
async def get_grabber_status(
    current_user: dict = Depends(get_current_user)
) -> GrabberStatus:
    """Get current grabber status"""
    return _grabber_status


@router.post("/grabber/stop")
async def stop_grabber(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Stop the running grabber"""
    global _grabber_task, _grabber_status
    
    try:
        if not _grabber_status.active:
            raise HTTPException(status_code=409, detail="Grabber is not running")
        
        if _grabber_task and not _grabber_task.done():
            _grabber_task.cancel()
            try:
                await _grabber_task
            except asyncio.CancelledError:
                pass
        
        _grabber_status.active = False
        _grabber_status.current_operation = "Stopped by user"
        
        logger.info("Grabber stopped by user", user=current_user.get('sub'))
        
        return {"message": "Grabber stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to stop grabber", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lists")
async def upload_list(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Upload a new domain/target list"""
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith(('.txt', '.list')):
            raise HTTPException(
                status_code=400, 
                detail="Only .txt and .list files are supported"
            )
        
        # Read and validate file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Count valid lines
        lines = [line.strip() for line in content_str.split('\n') if line.strip()]
        if not lines:
            raise HTTPException(status_code=400, detail="List file is empty")
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        
        # Save to filesystem
        file_path = grabber.data_dir / safe_filename
        with open(file_path, 'w') as f:
            f.write(content_str)
        
        # Determine category
        filename_lower = file.filename.lower()
        if 'wordlist' in filename_lower or 'paths' in filename_lower:
            category = 'wordlists'
        elif 'ip' in filename_lower or 'ranges' in filename_lower:
            category = 'ip_lists'
        else:
            category = 'targets'
        
        # Create list info
        list_info = ListInfo(
            id=str(hash(safe_filename)),
            name=Path(file.filename).stem,
            filename=safe_filename,
            category=category,
            size=len(lines),
            file_size=len(content),
            created_at=datetime.now(timezone.utc)
        )
        
        logger.info("List uploaded", 
                   filename=safe_filename,
                   category=category,
                   size=len(lines),
                   user=current_user.get('sub'))
        
        return {
            "id": list_info.id,
            "filename": safe_filename,
            "original_filename": file.filename,
            "category": category,
            "size": len(lines),
            "file_size": len(content),
            "message": f"List '{file.filename}' uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload list", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lists")
async def list_domain_lists(
    current_user: dict = Depends(get_current_user)
) -> List[ListInfo]:
    """List available domain/target lists"""
    try:
        lists = []
        
        # Scan data directory for files
        if grabber.data_dir.exists():
            for file_path in grabber.data_dir.iterdir():
                if file_path.is_file() and file_path.suffix in ['.txt', '.list']:
                    # Count lines
                    try:
                        with open(file_path, 'r') as f:
                            line_count = sum(1 for line in f if line.strip())
                    except:
                        line_count = 0
                    
                    # Determine category
                    filename = file_path.name.lower()
                    if 'wordlist' in filename or 'paths' in filename:
                        category = 'wordlists'
                    elif 'ip' in filename or 'ranges' in filename:
                        category = 'ip_lists'
                    else:
                        category = 'targets'
                    
                    list_info = ListInfo(
                        id=str(hash(file_path.name)),  # Simple ID generation
                        name=file_path.stem,
                        filename=file_path.name,
                        category=category,
                        size=line_count,
                        file_size=file_path.stat().st_size,
                        created_at=datetime.fromtimestamp(file_path.stat().st_ctime, tz=timezone.utc)
                    )
                    lists.append(list_info)
        
        return sorted(lists, key=lambda x: x.created_at, reverse=True)
        
    except Exception as e:
        logger.error("Failed to list domain lists", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/lists/{list_id}")
async def delete_list(
    list_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete a domain list file"""
    try:
        # Find the file by list_id (hash-based)
        found_file = None
        for file_path in grabber.data_dir.iterdir():
            if file_path.is_file() and str(hash(file_path.name)) == list_id:
                found_file = file_path
                break
        
        if not found_file:
            raise HTTPException(status_code=404, detail="List not found")
        
        # Delete the file
        found_file.unlink()
        
        logger.info("Domain list deleted", 
                   filename=found_file.name,
                   user=current_user.get('sub'))
        
        return {"message": f"List '{found_file.name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete list", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))