"""IP Generator API endpoints for httpxCloud v1 Phase 1"""

import ipaddress
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Any
from fastapi import APIRouter, HTTPException, status
import structlog

from ..core.models import IPGeneratorRequest, ListItem
from .lists import lists_storage, LISTS_DIR  # Reuse lists storage

logger = structlog.get_logger()

router = APIRouter(prefix="/ipgen", tags=["ip-generator"])


def parse_cidr(cidr: str) -> ipaddress.IPv4Network:
    """Parse and validate CIDR notation"""
    try:
        return ipaddress.IPv4Network(cidr, strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        raise ValueError(f"Invalid CIDR '{cidr}': {str(e)}")


def generate_unique_ips(cidrs: List[str], count: int) -> List[str]:
    """
    Generate unique IP addresses from given CIDR ranges
    
    Args:
        cidrs: List of CIDR notation strings (e.g., ['192.168.1.0/24', '10.0.0.0/16'])
        count: Number of unique IPs to generate
        
    Returns:
        List of unique IP addresses as strings
        
    Raises:
        ValueError: If CIDR is invalid or not enough IPs available
    """
    # Parse and validate all CIDRs
    networks = []
    total_available = 0
    
    for cidr in cidrs:
        try:
            network = parse_cidr(cidr)
            networks.append(network)
            total_available += network.num_addresses
        except ValueError as e:
            raise ValueError(f"Invalid CIDR '{cidr}': {str(e)}")
    
    # Check if we have enough IPs
    if total_available < count:
        raise ValueError(f"Not enough IP addresses available. Requested: {count}, Available: {total_available}")
    
    # Generate unique IPs
    generated_ips: Set[str] = set()
    attempts = 0
    max_attempts = count * 10  # Prevent infinite loops
    
    while len(generated_ips) < count and attempts < max_attempts:
        # Randomly select a network weighted by size
        weights = [net.num_addresses for net in networks]
        network = random.choices(networks, weights=weights)[0]
        
        # Generate random IP from selected network
        network_size = network.num_addresses
        random_offset = random.randint(0, network_size - 1)
        ip = str(network[random_offset])
        
        # Skip network and broadcast addresses for /31 and smaller subnets
        if network.prefixlen <= 30:
            if ip in [str(network.network_address), str(network.broadcast_address)]:
                attempts += 1
                continue
        
        generated_ips.add(ip)
        attempts += 1
    
    if len(generated_ips) < count:
        logger.warning("Could not generate requested number of unique IPs", 
                      requested=count, generated=len(generated_ips), attempts=attempts)
    
    return list(generated_ips)


@router.post("/")
async def generate_ip_list(request: IPGeneratorRequest) -> Dict[str, Any]:
    """
    Generate unique IP addresses from CIDR ranges and save as a list
    
    Creates a new list containing unique IP addresses generated from the provided CIDR ranges.
    The generated list can be used in scans just like uploaded lists.
    """
    try:
        # Validate input
        if not request.cidrs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one CIDR range is required"
            )
        
        if request.count <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Count must be greater than 0"
            )
        
        if request.count > 1000000:  # 1 million limit for Phase 1
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Count cannot exceed 1,000,000 IPs in Phase 1"
            )
        
        # Validate CIDR ranges and calculate total available IPs
        total_available = 0
        validated_cidrs = []
        
        for cidr in request.cidrs:
            try:
                network = parse_cidr(cidr)
                validated_cidrs.append(cidr)
                total_available += network.num_addresses
                
                # Log network info
                logger.debug("CIDR validated", 
                           cidr=cidr, 
                           network_address=str(network.network_address),
                           broadcast_address=str(network.broadcast_address),
                           num_addresses=network.num_addresses)
                           
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid CIDR '{cidr}': {str(e)}"
                )
        
        # Check if enough IPs are available
        if total_available < request.count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient IP addresses. Requested: {request.count:,}, Available: {total_available:,}"
            )
        
        logger.info("Starting IP generation", 
                   name=request.name,
                   cidrs=request.cidrs,
                   count=request.count,
                   total_available=total_available)
        
        # Generate unique IPs
        try:
            ip_addresses = generate_unique_ips(request.cidrs, request.count)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Create file to store IPs
        list_id = str(uuid.uuid4())
        filename = f"{list_id}_generated_ips.txt"
        file_path = LISTS_DIR / filename
        
        # Write IPs to file
        with open(file_path, 'w', encoding='utf-8') as f:
            for ip in ip_addresses:
                f.write(f"{ip}\n")
        
        # Create list item and add to storage
        list_item = ListItem(
            id=list_id,
            name=request.name,
            description=f"Generated from CIDRs: {', '.join(request.cidrs)}",
            size=len(ip_addresses),
            created_at=datetime.now(timezone.utc),
            file_path=str(file_path)
        )
        
        lists_storage[list_id] = list_item
        
        logger.info("IP list generated successfully", 
                   list_id=list_id,
                   name=request.name,
                   generated_count=len(ip_addresses),
                   requested_count=request.count,
                   file_path=str(file_path))
        
        return {
            "list_id": list_id,
            "name": request.name,
            "description": list_item.description,
            "generated_count": len(ip_addresses),
            "requested_count": request.count,
            "cidrs": request.cidrs,
            "total_available_ips": total_available,
            "created_at": list_item.created_at.isoformat(),
            "message": f"Generated {len(ip_addresses):,} unique IP addresses and saved as list '{request.name}'"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate IP list", 
                    name=request.name if hasattr(request, 'name') else "unknown",
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate IP list: {str(e)}"
        )


@router.post("/validate")
async def validate_cidrs(cidrs: List[str]) -> Dict[str, Any]:
    """
    Validate CIDR ranges and return statistics
    
    Useful for preview before generating IPs
    """
    try:
        if not cidrs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one CIDR range is required"
            )
        
        results = []
        total_ips = 0
        
        for cidr in cidrs:
            try:
                network = parse_cidr(cidr)
                cidr_info = {
                    "cidr": cidr,
                    "valid": True,
                    "network_address": str(network.network_address),
                    "broadcast_address": str(network.broadcast_address),
                    "num_addresses": network.num_addresses,
                    "prefix_length": network.prefixlen,
                    "is_private": network.is_private,
                    "is_multicast": network.is_multicast,
                    "is_reserved": network.is_reserved,
                    "error": None
                }
                total_ips += network.num_addresses
                
            except ValueError as e:
                cidr_info = {
                    "cidr": cidr,
                    "valid": False,
                    "error": str(e),
                    "num_addresses": 0
                }
            
            results.append(cidr_info)
        
        valid_cidrs = [r for r in results if r["valid"]]
        invalid_cidrs = [r for r in results if not r["valid"]]
        
        return {
            "total_cidrs": len(cidrs),
            "valid_cidrs": len(valid_cidrs),
            "invalid_cidrs": len(invalid_cidrs),
            "total_available_ips": total_ips,
            "results": results,
            "summary": {
                "largest_network": max((r["num_addresses"] for r in valid_cidrs), default=0),
                "smallest_network": min((r["num_addresses"] for r in valid_cidrs), default=0),
                "private_networks": len([r for r in valid_cidrs if r.get("is_private")]),
                "public_networks": len([r for r in valid_cidrs if not r.get("is_private", True)])
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate CIDRs", cidrs=cidrs, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate CIDRs: {str(e)}"
        )


@router.get("/examples")
async def get_cidr_examples() -> Dict[str, Any]:
    """
    Get example CIDR ranges for different use cases
    """
    return {
        "private_networks": {
            "description": "Private IP ranges (RFC 1918)",
            "cidrs": [
                "192.168.0.0/16",   # 65,536 IPs
                "172.16.0.0/12",    # 1,048,576 IPs  
                "10.0.0.0/8"        # 16,777,216 IPs
            ]
        },
        "public_clouds": {
            "description": "Common public cloud IP ranges (examples)",
            "cidrs": [
                "13.107.42.0/24",   # Microsoft
                "52.96.0.0/12",     # AWS
                "35.199.0.0/16",    # Google Cloud
                "13.104.0.0/14"     # Azure
            ]
        },
        "small_networks": {
            "description": "Small network ranges for testing",
            "cidrs": [
                "192.168.1.0/28",   # 16 IPs
                "10.0.0.0/29",      # 8 IPs
                "172.16.1.0/30"     # 4 IPs
            ]
        },
        "medium_networks": {
            "description": "Medium-sized networks",
            "cidrs": [
                "192.168.0.0/20",   # 4,096 IPs
                "10.1.0.0/22",      # 1,024 IPs
                "172.20.0.0/24"     # 256 IPs
            ]
        }
    }