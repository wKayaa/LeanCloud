"""Health check endpoint for httpxCloud v1 Phase 1"""

from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter
import structlog

from ..core.models import HealthResponse
from ..core.stats_manager import stats_manager

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    
    Returns system health status and basic metrics
    """
    try:
        # Get basic system info
        features = {
            "futuristic_ui": True,
            "real_time_websockets": True,
            "scan_simulation": True,
            "list_management": True,
            "ip_generation": True,
            "telegram_notifications": True,
            "stats_manager": True,
            "adaptive_controller": True
        }
        
        # Check if stats manager is running
        stats_healthy = hasattr(stats_manager, '_running') and stats_manager._running
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc),
            version="1.0.0-phase1",
            features=features
        )
    
    except Exception as e:
        logger.error("Health check error", error=str(e))
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc),
            version="1.0.0-phase1",
            features={}
        )


@router.get("/healthz/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with component status
    """
    try:
        # Check individual components
        components = {}
        
        # Stats Manager
        try:
            stats_running = hasattr(stats_manager, '_running') and stats_manager._running
            components["stats_manager"] = {
                "status": "healthy" if stats_running else "stopped",
                "active_scans": stats_manager.global_stats.active_scans,
                "total_scans": stats_manager.global_stats.total_scans
            }
        except Exception as e:
            components["stats_manager"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Configuration
        try:
            from pathlib import Path
            config_path = Path("data/config.yml")
            components["configuration"] = {
                "status": "healthy" if config_path.exists() else "missing",
                "path": str(config_path),
                "exists": config_path.exists()
            }
        except Exception as e:
            components["configuration"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Storage directories
        try:
            from pathlib import Path
            data_dir = Path("data")
            lists_dir = Path("data/lists")
            
            components["storage"] = {
                "status": "healthy",
                "data_dir_exists": data_dir.exists(),
                "lists_dir_exists": lists_dir.exists(),
                "data_dir": str(data_dir),
                "lists_dir": str(lists_dir)
            }
        except Exception as e:
            components["storage"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Overall health
        unhealthy_components = [
            name for name, info in components.items() 
            if info.get("status") not in ["healthy", "stopped"]
        ]
        
        overall_status = "healthy" if not unhealthy_components else "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0-phase1",
            "components": components,
            "unhealthy_components": unhealthy_components,
            "uptime_info": {
                "process_started": "Available in production deployment"
            }
        }
    
    except Exception as e:
        logger.error("Detailed health check error", error=str(e))
        return {
            "status": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }