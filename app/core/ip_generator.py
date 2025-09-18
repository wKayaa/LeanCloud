"""IP address generation utilities for creating unique, non-repeating IP lists"""

import ipaddress
import random
import tempfile
from typing import List, Set, Iterator, Optional, Tuple
from pathlib import Path
import structlog
import uuid
from datetime import datetime, timezone

logger = structlog.get_logger()


class IPGenerator:
    """Generate unique, non-repeating IP addresses from CIDR ranges"""
    
    def __init__(self):
        self.used_ips: Set[str] = set()
        
    def generate_from_cidrs(
        self, 
        cidrs: List[str], 
        count: int, 
        exclude_private: bool = True,
        exclude_reserved: bool = True
    ) -> Iterator[str]:
        """
        Generate unique IP addresses from CIDR ranges
        
        Args:
            cidrs: List of CIDR ranges (e.g., ['192.168.1.0/24', '10.0.0.0/8'])
            count: Number of IPs to generate
            exclude_private: Whether to exclude private IP ranges
            exclude_reserved: Whether to exclude reserved IP ranges
            
        Yields:
            Unique IP addresses as strings
        """
        all_networks = []
        total_ips = 0
        
        # Parse and validate CIDR ranges
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                all_networks.append(network)
                total_ips += network.num_addresses
                logger.debug("Added network", cidr=cidr, hosts=network.num_addresses)
            except ValueError as e:
                logger.warning("Invalid CIDR range", cidr=cidr, error=str(e))
                continue
        
        if not all_networks:
            logger.error("No valid CIDR ranges provided")
            return
        
        logger.info("IP generation started", 
                   total_networks=len(all_networks),
                   total_possible_ips=total_ips,
                   requested_count=count)
        
        generated_count = 0
        max_attempts = count * 10  # Prevent infinite loops
        attempts = 0
        
        while generated_count < count and attempts < max_attempts:
            attempts += 1
            
            # Select random network weighted by size
            network = self._select_weighted_network(all_networks)
            
            # Generate random IP from selected network
            try:
                ip = self._generate_random_ip_from_network(network)
                ip_str = str(ip)
                
                # Skip if already used
                if ip_str in self.used_ips:
                    continue
                
                # Apply filters
                if exclude_private and ip.is_private:
                    continue
                    
                if exclude_reserved and (ip.is_reserved or ip.is_loopback or ip.is_multicast):
                    continue
                
                # Add to used set and yield
                self.used_ips.add(ip_str)
                generated_count += 1
                yield ip_str
                
            except Exception as e:
                logger.debug("Failed to generate IP from network", 
                           network=str(network), error=str(e))
                continue
        
        logger.info("IP generation completed", 
                   generated=generated_count, 
                   attempts=attempts)
    
    def _select_weighted_network(self, networks: List[ipaddress.IPv4Network]) -> ipaddress.IPv4Network:
        """Select network with probability proportional to its size"""
        total_weight = sum(net.num_addresses for net in networks)
        random_weight = random.randint(1, total_weight)
        
        current_weight = 0
        for network in networks:
            current_weight += network.num_addresses
            if random_weight <= current_weight:
                return network
        
        return networks[0]  # Fallback
    
    def _generate_random_ip_from_network(self, network: ipaddress.IPv4Network) -> ipaddress.IPv4Address:
        """Generate random IP address from network"""
        # Get random host from network
        hosts = list(network.hosts()) if network.num_addresses > 2 else [network.network_address]
        if not hosts:
            hosts = [network.network_address]
        
        return random.choice(hosts)
    
    def preview_generation(
        self, 
        cidrs: List[str], 
        count: int = 10,
        exclude_private: bool = True,
        exclude_reserved: bool = True
    ) -> List[str]:
        """
        Preview IP generation without affecting the used IPs set
        
        Args:
            cidrs: CIDR ranges to generate from
            count: Number of preview IPs
            exclude_private: Exclude private IPs
            exclude_reserved: Exclude reserved IPs
            
        Returns:
            List of preview IP addresses
        """
        # Create temporary generator to avoid affecting main state
        temp_generator = IPGenerator()
        temp_generator.used_ips = self.used_ips.copy()
        
        preview_ips = list(temp_generator.generate_from_cidrs(
            cidrs, count, exclude_private, exclude_reserved
        ))
        
        return preview_ips
    
    def save_to_file(
        self, 
        ips: List[str], 
        filename: Optional[str] = None,
        directory: str = "data/lists"
    ) -> Tuple[str, int]:
        """
        Save IP list to file
        
        Args:
            ips: List of IP addresses
            filename: Target filename (auto-generated if None)
            directory: Directory to save in
            
        Returns:
            Tuple of (filepath, file_size_bytes)
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ip_list_{timestamp}.txt"
        
        Path(directory).mkdir(parents=True, exist_ok=True)
        filepath = Path(directory) / filename
        
        # Write IPs to file (one per line)
        content = "\n".join(ips) + "\n"
        filepath.write_text(content, encoding='utf-8')
        
        file_size = filepath.stat().st_size
        
        logger.info("IP list saved", 
                   filepath=str(filepath), 
                   count=len(ips),
                   size_bytes=file_size)
        
        return str(filepath), file_size
    
    def estimate_generation_time(self, cidrs: List[str], count: int) -> dict:
        """
        Estimate generation parameters and time
        
        Args:
            cidrs: CIDR ranges
            count: Requested IP count
            
        Returns:
            Dictionary with estimation metrics
        """
        total_possible = 0
        valid_networks = 0
        
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                total_possible += network.num_addresses
                valid_networks += 1
            except ValueError:
                continue
        
        # Simple estimation
        if total_possible == 0:
            success_probability = 0
        else:
            success_probability = min(1.0, count / total_possible)
        
        # Rough time estimation (very approximate)
        estimated_seconds = max(1, count / 10000)  # Assume ~10k IPs/sec
        
        return {
            "valid_networks": valid_networks,
            "total_possible_ips": total_possible,
            "requested_count": count,
            "success_probability": success_probability,
            "estimated_seconds": estimated_seconds,
            "feasible": success_probability > 0.01  # At least 1% chance
        }


class IPListManager:
    """Manage stored IP lists in database and filesystem"""
    
    def __init__(self, storage_dir: str = "data/lists"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_ip_list(
        self,
        name: str,
        description: Optional[str],
        cidrs: List[str],
        count: int,
        exclude_private: bool = True,
        exclude_reserved: bool = True
    ) -> dict:
        """
        Create and store new IP list
        
        Args:
            name: List name
            description: Optional description
            cidrs: Source CIDR ranges
            count: Number of IPs to generate
            exclude_private: Exclude private IPs
            exclude_reserved: Exclude reserved IPs
            
        Returns:
            Dictionary with list metadata
        """
        from .database import get_db_session, IPListDB
        
        # Generate unique filename
        list_id = str(uuid.uuid4())
        filename = f"iplist_{list_id}.txt"
        filepath = self.storage_dir / filename
        
        # Generate IPs
        generator = IPGenerator()
        ips = list(generator.generate_from_cidrs(
            cidrs, count, exclude_private, exclude_reserved
        ))
        
        if not ips:
            raise ValueError("No IPs could be generated from the provided CIDR ranges")
        
        # Save to file
        file_path, file_size = generator.save_to_file(
            ips, filename, str(self.storage_dir)
        )
        
        # Save metadata to database
        db_entry = IPListDB(
            id=uuid.UUID(list_id),
            name=name,
            description=description,
            cidrs=cidrs,
            total_count=count,
            generated_count=len(ips),
            filename=filename,
            file_size=file_size,
            created_at=datetime.now(timezone.utc)
        )
        
        try:
            async with get_db_session() as session:
                session.add(db_entry)
                await session.commit()
                
            logger.info("IP list created", 
                       name=name, 
                       list_id=list_id,
                       generated_count=len(ips))
            
            return {
                "id": list_id,
                "name": name,
                "description": description,
                "cidrs": cidrs,
                "total_count": count,
                "generated_count": len(ips),
                "filename": filename,
                "file_size": file_size,
                "created_at": db_entry.created_at.isoformat()
            }
            
        except Exception as e:
            # Clean up file if database operation fails
            if filepath.exists():
                filepath.unlink()
            raise e
    
    async def list_ip_lists(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """Get all IP lists with pagination"""
        from .database import get_db_session, IPListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(IPListDB)
                .order_by(IPListDB.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            ip_lists = result.scalars().all()
            
            return [
                {
                    "id": str(ip_list.id),
                    "name": ip_list.name,
                    "description": ip_list.description,
                    "cidrs": ip_list.cidrs,
                    "total_count": ip_list.total_count,
                    "generated_count": ip_list.generated_count,
                    "filename": ip_list.filename,
                    "file_size": ip_list.file_size,
                    "created_at": ip_list.created_at.isoformat()
                }
                for ip_list in ip_lists
            ]
    
    async def get_ip_list(self, list_id: str) -> Optional[dict]:
        """Get specific IP list by ID"""
        from .database import get_db_session, IPListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(IPListDB).where(IPListDB.id == uuid.UUID(list_id))
            )
            
            ip_list = result.scalar_one_or_none()
            
            if not ip_list:
                return None
            
            return {
                "id": str(ip_list.id),
                "name": ip_list.name,
                "description": ip_list.description,
                "cidrs": ip_list.cidrs,
                "total_count": ip_list.total_count,
                "generated_count": ip_list.generated_count,
                "filename": ip_list.filename,
                "file_size": ip_list.file_size,
                "created_at": ip_list.created_at.isoformat()
            }
    
    async def delete_ip_list(self, list_id: str) -> bool:
        """Delete IP list and associated file"""
        from .database import get_db_session, IPListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(IPListDB).where(IPListDB.id == uuid.UUID(list_id))
            )
            
            ip_list = result.scalar_one_or_none()
            
            if not ip_list:
                return False
            
            # Delete file
            filepath = self.storage_dir / ip_list.filename
            if filepath.exists():
                filepath.unlink()
            
            # Delete database entry
            await session.delete(ip_list)
            await session.commit()
            
            logger.info("IP list deleted", list_id=list_id, name=ip_list.name)
            return True
    
    def get_file_path(self, filename: str) -> Path:
        """Get full file path for IP list"""
        return self.storage_dir / filename


# Global instance
ip_list_manager = IPListManager()