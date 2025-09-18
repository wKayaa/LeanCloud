"""Lists API endpoints for httpxCloud v1 Phase 1"""

import os
import uuid
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
import structlog

from ..core.models import ListItem, ListUploadRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/lists", tags=["lists"])

# Storage configuration
LISTS_DIR = Path("data/lists")
LISTS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory storage for Phase 1 (will be replaced with SQLite in later phases)
lists_storage: Dict[str, ListItem] = {}


def count_lines_in_file(file_path: Path) -> int:
    """Count non-empty lines in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


@router.get("/")
async def list_stored_lists() -> Dict[str, Any]:
    """
    Get all stored lists with metadata
    """
    try:
        lists = []
        for list_item in lists_storage.values():
            # Verify file still exists and get current size
            file_path = Path(list_item.file_path)
            if file_path.exists():
                current_size = count_lines_in_file(file_path)
                file_size_bytes = file_path.stat().st_size
                
                lists.append({
                    "id": list_item.id,
                    "name": list_item.name,
                    "description": list_item.description,
                    "size": current_size,
                    "file_size_bytes": file_size_bytes,
                    "created_at": list_item.created_at.isoformat(),
                    "file_path": str(file_path.relative_to(LISTS_DIR))
                })
            else:
                # File was deleted, remove from storage
                logger.warning("List file missing, removing from storage", 
                             list_id=list_item.id, file_path=list_item.file_path)
        
        # Sort by creation time (newest first)
        lists.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "lists": lists,
            "total": len(lists),
            "storage_path": str(LISTS_DIR)
        }
    
    except Exception as e:
        logger.error("Failed to list stored lists", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve lists: {str(e)}"
        )


@router.post("/upload")
async def upload_list(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None)
) -> Dict[str, Any]:
    """
    Upload a new list file (.txt format)
    
    Supports large files and handles various text encodings
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .txt files are supported"
            )
        
        # Generate unique ID and file path
        list_id = str(uuid.uuid4())
        safe_filename = f"{list_id}_{file.filename}"
        file_path = LISTS_DIR / safe_filename
        
        # Write file to disk
        file_size = 0
        line_count = 0
        
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                await f.write(chunk)
                file_size += len(chunk)
        
        # Count lines in the uploaded file
        line_count = count_lines_in_file(file_path)
        
        # Create list item
        list_item = ListItem(
            id=list_id,
            name=name,
            description=description,
            size=line_count,
            created_at=datetime.now(timezone.utc),
            file_path=str(file_path)
        )
        
        # Store in memory
        lists_storage[list_id] = list_item
        
        logger.info("List uploaded successfully", 
                   list_id=list_id,
                   name=name,
                   file_size=file_size,
                   line_count=line_count,
                   filename=file.filename)
        
        return {
            "id": list_id,
            "name": name,
            "description": description,
            "size": line_count,
            "file_size_bytes": file_size,
            "created_at": list_item.created_at.isoformat(),
            "message": f"List '{name}' uploaded successfully with {line_count} entries"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload list", 
                    filename=file.filename if file else "unknown",
                    error=str(e))
        
        # Clean up partial file if it exists
        if 'file_path' in locals() and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload list: {str(e)}"
        )


@router.delete("/{list_id}")
async def delete_list(list_id: str) -> Dict[str, str]:
    """
    Delete a stored list
    """
    if list_id not in lists_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    
    try:
        list_item = lists_storage[list_id]
        file_path = Path(list_item.file_path)
        
        # Delete file if it exists
        if file_path.exists():
            file_path.unlink()
            logger.info("List file deleted", file_path=str(file_path))
        
        # Remove from storage
        del lists_storage[list_id]
        
        logger.info("List deleted successfully", 
                   list_id=list_id, 
                   name=list_item.name)
        
        return {
            "message": f"List '{list_item.name}' deleted successfully"
        }
    
    except Exception as e:
        logger.error("Failed to delete list", list_id=list_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete list: {str(e)}"
        )


@router.get("/{list_id}")
async def get_list_details(list_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific list
    """
    if list_id not in lists_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    
    try:
        list_item = lists_storage[list_id]
        file_path = Path(list_item.file_path)
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List file not found on disk"
            )
        
        # Get current file stats
        stat = file_path.stat()
        current_size = count_lines_in_file(file_path)
        
        return {
            "id": list_item.id,
            "name": list_item.name,
            "description": list_item.description,
            "size": current_size,
            "file_size_bytes": stat.st_size,
            "created_at": list_item.created_at.isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "file_path": str(file_path.relative_to(LISTS_DIR))
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get list details", list_id=list_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get list details: {str(e)}"
        )


@router.get("/{list_id}/download")
async def download_list(list_id: str):
    """
    Download a stored list file
    """
    if list_id not in lists_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    
    try:
        list_item = lists_storage[list_id]
        file_path = Path(list_item.file_path)
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List file not found on disk"
            )
        
        # Return file for download
        return FileResponse(
            path=str(file_path),
            filename=f"{list_item.name}.txt",
            media_type="text/plain"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download list", list_id=list_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download list: {str(e)}"
        )


@router.get("/{list_id}/preview")
async def preview_list(list_id: str, lines: int = 50) -> Dict[str, Any]:
    """
    Preview the first N lines of a list
    """
    if list_id not in lists_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    
    try:
        list_item = lists_storage[list_id]
        file_path = Path(list_item.file_path)
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List file not found on disk"
            )
        
        # Read first N lines
        preview_lines = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= lines:
                    break
                line = line.strip()
                if line:
                    preview_lines.append(line)
        
        return {
            "list_id": list_id,
            "name": list_item.name,
            "preview_lines": len(preview_lines),
            "total_lines": list_item.size,
            "lines": preview_lines,
            "truncated": list_item.size > lines
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview list", list_id=list_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview list: {str(e)}"
        )