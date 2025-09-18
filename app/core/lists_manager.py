"""Lists management for storing and managing wordlists, target lists, and other text files"""

import aiofiles
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
import structlog
import hashlib

logger = structlog.get_logger()


class ListsManager:
    """Manage uploaded and stored lists (wordlists, targets, etc.)"""
    
    def __init__(self, storage_dir: str = "data/lists"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported list types
        self.LIST_TYPES = {
            'wordlist': {
                'name': 'Wordlist',
                'description': 'Path/directory wordlist for scanning',
                'extensions': ['.txt', '.list', '.wordlist']
            },
            'targets': {
                'name': 'Target List',
                'description': 'List of target URLs/domains',
                'extensions': ['.txt', '.list', '.targets']
            },
            'ips': {
                'name': 'IP List',
                'description': 'List of IP addresses',
                'extensions': ['.txt', '.list', '.ips']
            }
        }
    
    async def upload_list(
        self,
        name: str,
        original_filename: str,
        file_content: bytes,
        list_type: str = 'wordlist',
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload and store a new list
        
        Args:
            name: Display name for the list
            original_filename: Original filename from upload
            file_content: Raw file content
            list_type: Type of list (wordlist, targets, ips)
            description: Optional description
        
        Returns:
            Dictionary with list metadata
        """
        from .database import get_db_session, ListDB
        
        if list_type not in self.LIST_TYPES:
            raise ValueError(f"Invalid list type. Must be one of: {list(self.LIST_TYPES.keys())}")
        
        # Generate unique storage filename
        list_id = str(uuid.uuid4())
        file_extension = Path(original_filename).suffix or '.txt'
        storage_filename = f"{list_type}_{list_id}{file_extension}"
        storage_path = self.storage_dir / storage_filename
        
        # Validate and process content
        try:
            content_str = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Try other encodings
            for encoding in ['latin-1', 'cp1252']:
                try:
                    content_str = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("File encoding not supported. Please use UTF-8.")
        
        # Count non-empty lines
        lines = [line.strip() for line in content_str.splitlines()]
        non_empty_lines = [line for line in lines if line and not line.startswith('#')]
        items_count = len(non_empty_lines)
        
        if items_count == 0:
            raise ValueError("File contains no valid items")
        
        # Calculate file hash for deduplication
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check for duplicates
        async with get_db_session() as session:
            from sqlalchemy import select
            existing = await session.execute(
                select(ListDB).where(
                    (ListDB.name == name) | 
                    (ListDB.filename == storage_filename)
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"List with name '{name}' already exists")
        
        # Save file to storage
        async with aiofiles.open(storage_path, 'wb') as f:
            await f.write(file_content)
        
        file_size = storage_path.stat().st_size
        
        # Create database entry
        db_entry = ListDB(
            id=uuid.UUID(list_id),
            name=name,
            list_type=list_type,
            description=description,
            filename=storage_filename,
            original_filename=original_filename,
            items_count=items_count,
            file_size=file_size,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        try:
            async with get_db_session() as session:
                session.add(db_entry)
                await session.commit()
                
            logger.info("List uploaded", 
                       name=name, 
                       list_id=list_id,
                       type=list_type,
                       items_count=items_count,
                       file_size=file_size)
            
            return {
                "id": list_id,
                "name": name,
                "list_type": list_type,
                "description": description,
                "filename": storage_filename,
                "original_filename": original_filename,
                "items_count": items_count,
                "file_size": file_size,
                "created_at": db_entry.created_at.isoformat(),
                "updated_at": db_entry.updated_at.isoformat()
            }
            
        except Exception as e:
            # Clean up file if database operation fails
            if storage_path.exists():
                storage_path.unlink()
            raise e
    
    async def list_lists(
        self, 
        list_type: Optional[str] = None,
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get lists with optional filtering and pagination
        
        Args:
            list_type: Filter by list type
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of list metadata dictionaries
        """
        from .database import get_db_session, ListDB
        from sqlalchemy import select
        
        query = select(ListDB)
        
        if list_type:
            query = query.where(ListDB.list_type == list_type)
        
        query = query.order_by(ListDB.created_at.desc()).limit(limit).offset(offset)
        
        async with get_db_session() as session:
            result = await session.execute(query)
            lists = result.scalars().all()
            
            return [
                {
                    "id": str(list_obj.id),
                    "name": list_obj.name,
                    "list_type": list_obj.list_type,
                    "description": list_obj.description,
                    "filename": list_obj.filename,
                    "original_filename": list_obj.original_filename,
                    "items_count": list_obj.items_count,
                    "file_size": list_obj.file_size,
                    "created_at": list_obj.created_at.isoformat(),
                    "updated_at": list_obj.updated_at.isoformat()
                }
                for list_obj in lists
            ]
    
    async def get_list(self, list_id: str) -> Optional[Dict[str, Any]]:
        """Get specific list by ID"""
        from .database import get_db_session, ListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(ListDB).where(ListDB.id == uuid.UUID(list_id))
            )
            
            list_obj = result.scalar_one_or_none()
            
            if not list_obj:
                return None
            
            return {
                "id": str(list_obj.id),
                "name": list_obj.name,
                "list_type": list_obj.list_type,
                "description": list_obj.description,
                "filename": list_obj.filename,
                "original_filename": list_obj.original_filename,
                "items_count": list_obj.items_count,
                "file_size": list_obj.file_size,
                "created_at": list_obj.created_at.isoformat(),
                "updated_at": list_obj.updated_at.isoformat()
            }
    
    async def get_list_content(self, list_id: str, max_lines: int = 1000) -> Optional[List[str]]:
        """
        Get content of a list file
        
        Args:
            list_id: List ID
            max_lines: Maximum number of lines to return
        
        Returns:
            List of content lines or None if not found
        """
        list_info = await self.get_list(list_id)
        if not list_info:
            return None
        
        filepath = self.storage_dir / list_info['filename']
        if not filepath.exists():
            logger.warning("List file not found", list_id=list_id, filename=list_info['filename'])
            return None
        
        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                lines = []
                line_count = 0
                async for line in f:
                    if line_count >= max_lines:
                        break
                    line = line.strip()
                    if line and not line.startswith('#'):
                        lines.append(line)
                    line_count += 1
                
                return lines
                
        except Exception as e:
            logger.error("Failed to read list content", list_id=list_id, error=str(e))
            return None
    
    async def delete_list(self, list_id: str) -> bool:
        """Delete list and associated file"""
        from .database import get_db_session, ListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(ListDB).where(ListDB.id == uuid.UUID(list_id))
            )
            
            list_obj = result.scalar_one_or_none()
            
            if not list_obj:
                return False
            
            # Delete file
            filepath = self.storage_dir / list_obj.filename
            if filepath.exists():
                filepath.unlink()
            
            # Delete database entry
            await session.delete(list_obj)
            await session.commit()
            
            logger.info("List deleted", list_id=list_id, name=list_obj.name)
            return True
    
    async def update_list(
        self, 
        list_id: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update list metadata"""
        from .database import get_db_session, ListDB
        from sqlalchemy import select
        
        async with get_db_session() as session:
            result = await session.execute(
                select(ListDB).where(ListDB.id == uuid.UUID(list_id))
            )
            
            list_obj = result.scalar_one_or_none()
            
            if not list_obj:
                return None
            
            # Update fields
            if name is not None:
                list_obj.name = name
            if description is not None:
                list_obj.description = description
            
            list_obj.updated_at = datetime.now(timezone.utc)
            
            await session.commit()
            
            logger.info("List updated", list_id=list_id, name=list_obj.name)
            
            return {
                "id": str(list_obj.id),
                "name": list_obj.name,
                "list_type": list_obj.list_type,
                "description": list_obj.description,
                "filename": list_obj.filename,
                "original_filename": list_obj.original_filename,
                "items_count": list_obj.items_count,
                "file_size": list_obj.file_size,
                "created_at": list_obj.created_at.isoformat(),
                "updated_at": list_obj.updated_at.isoformat()
            }
    
    def get_file_path(self, filename: str) -> Path:
        """Get full file path for list"""
        return self.storage_dir / filename
    
    async def get_list_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored lists"""
        from .database import get_db_session, ListDB
        from sqlalchemy import select, func
        
        async with get_db_session() as session:
            # Total counts by type
            result = await session.execute(
                select(
                    ListDB.list_type,
                    func.count(ListDB.id).label('count'),
                    func.sum(ListDB.items_count).label('total_items'),
                    func.sum(ListDB.file_size).label('total_size')
                ).group_by(ListDB.list_type)
            )
            
            stats_by_type = {}
            total_lists = 0
            total_items = 0
            total_size = 0
            
            for row in result:
                stats_by_type[row.list_type] = {
                    'count': row.count,
                    'total_items': row.total_items or 0,
                    'total_size': row.total_size or 0
                }
                total_lists += row.count
                total_items += row.total_items or 0
                total_size += row.total_size or 0
            
            return {
                'total_lists': total_lists,
                'total_items': total_items,
                'total_size_bytes': total_size,
                'by_type': stats_by_type
            }
    
    def validate_list_content(self, content: str, list_type: str) -> Dict[str, Any]:
        """
        Validate list content based on type
        
        Args:
            content: File content as string
            list_type: Type of list to validate against
            
        Returns:
            Validation result with issues and statistics
        """
        lines = content.splitlines()
        valid_lines = []
        issues = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Type-specific validation
            if list_type == 'targets':
                # Basic URL/domain validation
                if not (line.startswith(('http://', 'https://')) or '.' in line):
                    issues.append(f"Line {line_num}: '{line}' doesn't look like a valid URL or domain")
                else:
                    valid_lines.append(line)
            
            elif list_type == 'ips':
                # IP address validation
                import ipaddress
                try:
                    ipaddress.ip_address(line)
                    valid_lines.append(line)
                except ValueError:
                    issues.append(f"Line {line_num}: '{line}' is not a valid IP address")
            
            elif list_type == 'wordlist':
                # Wordlist validation (pretty lenient)
                if len(line) > 1000:  # Reasonable path length limit
                    issues.append(f"Line {line_num}: Path too long ({len(line)} chars)")
                else:
                    valid_lines.append(line)
            
            else:
                # Generic validation
                valid_lines.append(line)
        
        return {
            'valid': len(issues) == 0,
            'total_lines': len(lines),
            'valid_items': len(valid_lines),
            'issues': issues,
            'issues_count': len(issues)
        }


# Global instance
lists_manager = ListsManager()