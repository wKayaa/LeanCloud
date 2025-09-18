"""WebSocket endpoints for httpxCloud v1 Phase 1"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any
from fastapi import WebSocket, WebSocketDisconnect
import structlog

from ..core.stats_manager import stats_manager
from ..core.models import WSEventType

logger = structlog.get_logger()


class WebSocketManager:
    """
    WebSocket connection manager for Phase 1
    
    Manages connections for scan-specific and dashboard updates
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.scan_connections: Dict[str, List[WebSocket]] = {}  # scan_id -> [websockets]
        self.dashboard_connections: List[WebSocket] = []
        
        # Connection metadata
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect_to_scan(self, websocket: WebSocket, scan_id: str):
        """Connect WebSocket to scan updates"""
        await websocket.accept()
        
        if scan_id not in self.scan_connections:
            self.scan_connections[scan_id] = []
        
        self.scan_connections[scan_id].append(websocket)
        self.connection_info[websocket] = {
            "type": "scan",
            "scan_id": scan_id,
            "connected_at": datetime.now(timezone.utc)
        }
        
        # Subscribe to stats manager
        stats_manager.subscribe_to_scan(scan_id, websocket)
        
        logger.info("WebSocket connected to scan", scan_id=scan_id)
    
    async def connect_to_dashboard(self, websocket: WebSocket):
        """Connect WebSocket to dashboard updates"""
        await websocket.accept()
        
        self.dashboard_connections.append(websocket)
        self.connection_info[websocket] = {
            "type": "dashboard",
            "connected_at": datetime.now(timezone.utc)
        }
        
        # Subscribe to stats manager
        stats_manager.subscribe_to_dashboard(websocket)
        
        logger.info("WebSocket connected to dashboard")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket and clean up"""
        if websocket not in self.connection_info:
            return
        
        info = self.connection_info[websocket]
        
        if info["type"] == "scan":
            scan_id = info["scan_id"]
            if scan_id in self.scan_connections and websocket in self.scan_connections[scan_id]:
                self.scan_connections[scan_id].remove(websocket)
                if not self.scan_connections[scan_id]:
                    del self.scan_connections[scan_id]
                
                stats_manager.unsubscribe_from_scan(scan_id, websocket)
                logger.info("WebSocket disconnected from scan", scan_id=scan_id)
        
        elif info["type"] == "dashboard":
            if websocket in self.dashboard_connections:
                self.dashboard_connections.remove(websocket)
                stats_manager.unsubscribe_from_dashboard(websocket)
                logger.info("WebSocket disconnected from dashboard")
        
        del self.connection_info[websocket]
    
    async def send_to_scan(self, scan_id: str, message: Dict[str, Any]):
        """Send message to all connections for a specific scan"""
        if scan_id not in self.scan_connections:
            return
        
        disconnected = []
        for websocket in self.scan_connections[scan_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug("Failed to send to scan websocket", scan_id=scan_id, error=str(e))
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(ws)
    
    async def send_to_dashboard(self, message: Dict[str, Any]):
        """Send message to all dashboard connections"""
        disconnected = []
        for websocket in self.dashboard_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug("Failed to send to dashboard websocket", error=str(e))
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(ws)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_scan_connections": sum(len(connections) for connections in self.scan_connections.values()),
            "scan_channels": len(self.scan_connections),
            "dashboard_connections": len(self.dashboard_connections),
            "total_connections": len(self.connection_info),
            "channels": {
                scan_id: len(connections) 
                for scan_id, connections in self.scan_connections.items()
            }
        }


# Global WebSocket manager
ws_manager = WebSocketManager()


async def websocket_scan_handler(websocket: WebSocket, scan_id: str):
    """
    WebSocket handler for scan-specific updates
    
    Endpoint: /ws/scans/{scan_id}
    """
    try:
        await ws_manager.connect_to_scan(websocket, scan_id)
        
        # Send initial scan status if available
        scan_stats = stats_manager.get_scan_stats(scan_id)
        if scan_stats:
            initial_message = {
                "type": WSEventType.SCAN_STATUS.value,
                "scan_id": scan_id,
                "data": scan_stats.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_json(initial_message)
        
        # Listen for client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await handle_client_message(websocket, scan_id, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                error_message = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_json(error_message)
            except Exception as e:
                logger.error("Error processing WebSocket message", scan_id=scan_id, error=str(e))
                error_message = {
                    "type": "error",
                    "message": f"Error processing message: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_json(error_message)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket scan handler error", scan_id=scan_id, error=str(e))
    finally:
        ws_manager.disconnect(websocket)


async def websocket_dashboard_handler(websocket: WebSocket):
    """
    WebSocket handler for dashboard updates
    
    Endpoint: /ws/dashboard
    """
    try:
        await ws_manager.connect_to_dashboard(websocket)
        
        # Send connection acknowledgment
        welcome_message = {
            "type": "connected",
            "message": "Connected to dashboard",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_json(welcome_message)
        
        # Listen for client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await handle_dashboard_message(websocket, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                error_message = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_json(error_message)
            except Exception as e:
                logger.error("Error processing dashboard WebSocket message", error=str(e))
                error_message = {
                    "type": "error",
                    "message": f"Error processing message: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_json(error_message)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket dashboard handler error", error=str(e))
    finally:
        ws_manager.disconnect(websocket)


async def handle_client_message(websocket: WebSocket, scan_id: str, message: Dict[str, Any]):
    """Handle messages from scan WebSocket clients"""
    message_type = message.get("type")
    
    if message_type == WSEventType.PING.value:
        # Respond to ping with pong
        pong_message = {
            "type": WSEventType.PONG.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_json(pong_message)
    
    elif message_type == WSEventType.GET_SCAN_STATUS.value:
        # Send current scan status
        scan_stats = stats_manager.get_scan_stats(scan_id)
        if scan_stats:
            status_message = {
                "type": WSEventType.SCAN_STATUS.value,
                "scan_id": scan_id,
                "data": scan_stats.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_json(status_message)
        else:
            error_message = {
                "type": "error",
                "message": f"Scan {scan_id} not found",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_json(error_message)
    
    else:
        logger.debug("Unknown message type from scan client", 
                    scan_id=scan_id, message_type=message_type)


async def handle_dashboard_message(websocket: WebSocket, message: Dict[str, Any]):
    """Handle messages from dashboard WebSocket clients"""
    message_type = message.get("type")
    
    if message_type == WSEventType.PING.value:
        # Respond to ping with pong
        pong_message = {
            "type": WSEventType.PONG.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_json(pong_message)
    
    elif message_type == "get_stats":
        # Send current global stats
        stats_message = {
            "type": WSEventType.DASHBOARD_STATS.value,
            "data": stats_manager.global_stats.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_json(stats_message)
    
    elif message_type == "get_connection_stats":
        # Send WebSocket connection statistics
        conn_stats = ws_manager.get_connection_stats()
        stats_message = {
            "type": "connection_stats",
            "data": conn_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_json(stats_message)
    
    else:
        logger.debug("Unknown message type from dashboard client", message_type=message_type)


# Utility functions for broadcasting (used by other modules)

async def broadcast_scan_update(scan_id: str, update_type: str, data: Dict[str, Any]):
    """Broadcast update to all scan subscribers"""
    message = {
        "type": update_type,
        "scan_id": scan_id,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.send_to_scan(scan_id, message)


async def broadcast_dashboard_update(update_type: str, data: Dict[str, Any]):
    """Broadcast update to all dashboard subscribers"""
    message = {
        "type": update_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.send_to_dashboard(message)


async def broadcast_scan_hit(scan_id: str, hit_data: Dict[str, Any]):
    """Broadcast new hit to scan subscribers"""
    await broadcast_scan_update(scan_id, WSEventType.SCAN_HIT.value, hit_data)


async def broadcast_scan_log(scan_id: str, log_message: str, level: str = "info"):
    """Broadcast log message to scan subscribers"""
    log_data = {
        "message": log_message,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await broadcast_scan_update(scan_id, WSEventType.SCAN_LOG.value, log_data)