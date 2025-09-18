"""Grabber API endpoints for domain generation"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Any
import uuid
from datetime import datetime
import random

from ..core.auth import get_current_user, require_admin
from ..core.models import GrabberStatus, DomainList

router = APIRouter()

# Global grabber state
grabber_state = {
    "status": "stopped",
    "progress": 0,
    "domains_generated": 0,
    "current_seed": None,
    "eta_seconds": None,
    "task": None
}

# In-memory domain lists storage (replace with database in production)
domain_lists: Dict[str, DomainList] = {}


@router.post("/grabber/start")
async def start_grabber(
    seeds: List[str] = [],
    max_domains: int = 1000,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Start the domain grabber worker"""
    
    if grabber_state["status"] == "running":
        raise HTTPException(status_code=400, detail="Grabber is already running")
    
    # Start the grabber task
    grabber_state["status"] = "running"
    grabber_state["progress"] = 0
    grabber_state["domains_generated"] = 0
    grabber_state["current_seed"] = seeds[0] if seeds else "auto"
    grabber_state["eta_seconds"] = max_domains // 10  # Estimate 10 domains per second
    
    # Start async task
    grabber_state["task"] = asyncio.create_task(
        _run_grabber_worker(seeds, max_domains)
    )
    
    return {
        "message": "Grabber started successfully",
        "status": "running",
        "config": {
            "seeds": seeds,
            "max_domains": max_domains
        }
    }


@router.get("/grabber/status")
async def get_grabber_status(
    current_user: Dict = Depends(get_current_user)
) -> GrabberStatus:
    """Get current grabber status"""
    
    return GrabberStatus(
        status=grabber_state["status"],
        progress=grabber_state["progress"],
        domains_generated=grabber_state["domains_generated"],
        current_seed=grabber_state["current_seed"],
        eta_seconds=grabber_state["eta_seconds"]
    )


@router.post("/grabber/stop")
async def stop_grabber(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Stop the grabber worker"""
    
    if grabber_state["status"] != "running":
        return {"message": "Grabber is not running", "status": "stopped"}
    
    # Cancel the task if it exists
    if grabber_state["task"]:
        grabber_state["task"].cancel()
        grabber_state["task"] = None
    
    grabber_state["status"] = "stopped"
    grabber_state["progress"] = 0
    grabber_state["current_seed"] = None
    
    return {
        "message": "Grabber stopped successfully", 
        "status": "stopped"
    }


@router.get("/lists")
async def get_domain_lists(
    current_user: Dict = Depends(get_current_user)
) -> List[DomainList]:
    """Get all available domain lists"""
    
    return list(domain_lists.values())


@router.delete("/lists/{list_id}")
async def delete_domain_list(
    list_id: str,
    current_user: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """Delete a domain list"""
    
    if list_id not in domain_lists:
        raise HTTPException(status_code=404, detail="Domain list not found")
    
    del domain_lists[list_id]
    
    return {
        "message": f"Domain list {list_id} deleted successfully",
        "status": "success"
    }


async def _run_grabber_worker(seeds: List[str], max_domains: int):
    """Background worker that generates domains"""
    
    try:
        generated_domains = []
        
        # Simple domain generation logic
        base_domains = seeds if seeds else [
            "example.com", "test.com", "demo.org", "sample.net"
        ]
        
        prefixes = ["api", "app", "www", "mail", "admin", "dev", "staging", "prod"]
        suffixes = [".com", ".org", ".net", ".io", ".co"]
        
        for i in range(max_domains):
            if grabber_state["status"] != "running":
                break
                
            # Generate a domain
            if seeds:
                base = random.choice(base_domains)
                domain = f"{random.choice(prefixes)}.{base}"
            else:
                # Generate completely new domains
                name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
                domain = f"{name}{random.choice(suffixes)}"
            
            generated_domains.append(domain)
            
            # Update progress
            grabber_state["domains_generated"] = len(generated_domains)
            grabber_state["progress"] = int((len(generated_domains) / max_domains) * 100)
            grabber_state["eta_seconds"] = max(0, (max_domains - len(generated_domains)) // 10)
            
            # Simulate work delay
            await asyncio.sleep(0.1)
        
        # Save generated domains as a list
        if generated_domains:
            list_id = str(uuid.uuid4())
            filename = f"grabber_domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            domain_list = DomainList(
                id=list_id,
                filename=filename,
                size=len('\n'.join(generated_domains).encode()),
                domain_count=len(generated_domains),
                source="grabber"
            )
            
            domain_lists[list_id] = domain_list
        
        # Mark as completed
        grabber_state["status"] = "completed"
        grabber_state["progress"] = 100
        grabber_state["eta_seconds"] = 0
        
    except asyncio.CancelledError:
        grabber_state["status"] = "stopped"
        grabber_state["progress"] = 0
    except Exception as e:
        grabber_state["status"] = "error"
        grabber_state["current_seed"] = f"Error: {str(e)}"


# Helper function to add sample domain lists
def add_sample_domain_lists():
    """Add sample domain lists for testing"""
    
    sample_lists = [
        {
            "filename": "common_domains.txt",
            "domain_count": 1500,
            "size": 25000
        },
        {
            "filename": "tech_companies.txt", 
            "domain_count": 850,
            "size": 15200
        },
        {
            "filename": "government_sites.txt",
            "domain_count": 320,
            "size": 8900
        }
    ]
    
    for sample in sample_lists:
        list_id = str(uuid.uuid4())
        domain_list = DomainList(
            id=list_id,
            filename=sample["filename"],
            domain_count=sample["domain_count"],
            size=sample["size"],
            source="upload"
        )
        domain_lists[list_id] = domain_list


# Initialize with sample domain lists when module loads
add_sample_domain_lists()