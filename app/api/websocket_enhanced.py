"""Enhanced WebSocket system for httpxCloud v1 with real-time features"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import structlog

from ..core.auth import auth_manager
from ..core.redis_manager import get_redis
from ..core.models import WSEventType, WebSocketMessage
from ..core.metrics import metrics
from ..core.scanner_enhanced import enhanced_scanner

logger = structlog.get_logger()


class EnhancedConnectionManager:
    """Enhanced connection manager with channel support"""
    
    def __init__(self):
        # All active connections
        self.active_connections: List[WebSocket] = []
        
        # Scan-specific subscribers
        self.scan_subscribers: Dict[str, Set[WebSocket]] = {}
        
        # Dashboard subscribers (global stats)
        self.dashboard_subscribers: Set[WebSocket] = set()
        
        # Redis pubsub listeners
        self.redis_listeners: Dict[str, asyncio.Task] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        """Accept WebSocket connection and set up listeners"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc),
            "subscriptions": set()
        }
        
        # Update metrics
        metrics.websocket_connected()
        
        # Start Redis listeners if not already started
        if not self.redis_listeners:
            await self._start_redis_listeners()
        
        logger.info("WebSocket connected", user_id=user_id, 
                   total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from scan subscriptions
        for scan_id in list(self.scan_subscribers.keys()):
            if websocket in self.scan_subscribers[scan_id]:
                self.scan_subscribers[scan_id].discard(websocket)
                if not self.scan_subscribers[scan_id]:
                    del self.scan_subscribers[scan_id]
        
        # Remove from dashboard subscriptions
        self.dashboard_subscribers.discard(websocket)
        
        # Clean up metadata
        self.connection_metadata.pop(websocket, None)
        
        # Update metrics
        metrics.websocket_disconnected()
        
        logger.info("WebSocket disconnected", 
                   total_connections=len(self.active_connections))
    
    async def subscribe_to_scan(self, websocket: WebSocket, scan_id: str):
        """Subscribe to scan-specific events"""
        if scan_id not in self.scan_subscribers:
            self.scan_subscribers[scan_id] = set()
        
        self.scan_subscribers[scan_id].add(websocket)
        
        # Update connection metadata
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["subscriptions"].add(f"scan:{scan_id}")
        
        logger.debug("Subscribed to scan", scan_id=scan_id, 
                    subscribers=len(self.scan_subscribers[scan_id]))
    
    async def subscribe_to_dashboard(self, websocket: WebSocket):
        """Subscribe to dashboard events"""
        self.dashboard_subscribers.add(websocket)
        
        # Update connection metadata
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["subscriptions"].add("dashboard")
        
        logger.debug("Subscribed to dashboard", 
                    subscribers=len(self.dashboard_subscribers))
    
    async def send_to_connection(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to specific connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning("Failed to send message to connection", error=str(e))
            self.disconnect(websocket)
    
    async def broadcast_to_scan_subscribers(self, scan_id: str, message: Dict[str, Any]):
        """Broadcast message to scan subscribers"""
        if scan_id not in self.scan_subscribers:
            return
        
        disconnected = []
        for websocket in self.scan_subscribers[scan_id]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected connections
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # Update metrics
        metrics.websocket_message_sent(message.get("type", "unknown"))
        
        logger.debug("Broadcasted to scan subscribers", scan_id=scan_id, 
                    recipients=len(self.scan_subscribers[scan_id]) - len(disconnected))
    
    async def broadcast_to_dashboard_subscribers(self, message: Dict[str, Any]):
        """Broadcast message to dashboard subscribers"""
        disconnected = []
        for websocket in self.dashboard_subscribers:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected connections
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # Update metrics
        metrics.websocket_message_sent(message.get("type", "unknown"))
        
        logger.debug("Broadcasted to dashboard subscribers", 
                    recipients=len(self.dashboard_subscribers) - len(disconnected))
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connections"""
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected connections
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # Update metrics
        metrics.websocket_message_sent(message.get("type", "unknown"))
        
        logger.debug("Broadcasted to all connections", 
                    recipients=len(self.active_connections) - len(disconnected))
    
    async def _start_redis_listeners(self):
        """Start Redis pub/sub listeners with graceful degradation"""
        try:
            redis = get_redis()
            
            # Check if Redis is healthy before starting listeners
            if not await redis.is_healthy():
                logger.warning("Redis is unavailable - WebSocket will work in degraded mode")
                # Send degraded mode notification to all connections
                await self.broadcast_to_all({
                    "type": "warning",
                    "message": "Real-time updates disabled (Redis offline)",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                return
            
            # Listen for scan events
            scan_events_task = asyncio.create_task(
                self._listen_scan_events(redis)
            )
            self.redis_listeners["scan_events"] = scan_events_task
            
            # Listen for dashboard stats
            dashboard_stats_task = asyncio.create_task(
                self._listen_dashboard_stats(redis)
            )
            self.redis_listeners["dashboard_stats"] = dashboard_stats_task
            
            logger.info("Redis listeners started")
            
        except Exception as e:
            logger.error("Failed to start Redis listeners - continuing in degraded mode", error=str(e))
            # Send degraded mode notification
            await self.broadcast_to_all({
                "type": "warning", 
                "message": "Real-time updates disabled (Redis connection failed)",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def _listen_scan_events(self, redis):
        """Listen for scan events from Redis with error handling"""
        try:
            pubsub = await redis.subscribe("scan_events:*")
            if not pubsub:
                logger.warning("Failed to subscribe to scan events - Redis unavailable")
                return
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Extract scan_id from channel
                        channel = message["channel"]
                        scan_id = channel.split(":")[-1]
                        
                        # Parse event data
                        event_data = json.loads(message["data"])
                        
                        # Broadcast to scan subscribers
                        await self.broadcast_to_scan_subscribers(scan_id, event_data)
                        
                    except Exception as e:
                        logger.error("Failed to process scan event", error=str(e))
        
        except Exception as e:
            logger.error("Scan events listener failed", error=str(e))
    
    async def _listen_dashboard_stats(self, redis):
        """Listen for dashboard stats from Redis with error handling"""
        try:
            pubsub = await redis.subscribe("dashboard_stats")
            if not pubsub:
                logger.warning("Failed to subscribe to dashboard stats - Redis unavailable")
                return
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Parse stats data
                        stats_data = json.loads(message["data"])
                        
                        # Add event type
                        stats_data["type"] = WSEventType.DASHBOARD_STATS.value
                        
                        # Broadcast to dashboard subscribers
                        await self.broadcast_to_dashboard_subscribers(stats_data)
                        
                    except Exception as e:
                        logger.error("Failed to process dashboard stats", error=str(e))
        
        except Exception as e:
            logger.error("Dashboard stats listener failed", error=str(e))
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        scan_subscriptions = sum(len(subs) for subs in self.scan_subscribers.values())
        
        return {
            "total_connections": len(self.active_connections),
            "scan_subscriptions": scan_subscriptions,
            "dashboard_subscriptions": len(self.dashboard_subscribers),
            "active_scan_channels": len(self.scan_subscribers),
            "redis_listeners": len(self.redis_listeners)
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        # Cancel Redis listeners
        for task in self.redis_listeners.values():
            task.cancel()
        
        # Close all connections
        for websocket in self.active_connections[:]:
            try:
                await websocket.close()
            except Exception:
                pass
        
        self.active_connections.clear()
        self.scan_subscribers.clear()
        self.dashboard_subscribers.clear()
        self.connection_metadata.clear()
        
        logger.info("Connection manager cleaned up")


# Global connection manager
manager = EnhancedConnectionManager()


async def websocket_scan_endpoint(websocket: WebSocket, scan_id: str, token: str = None):
    """WebSocket endpoint for scan-specific events"""
    user_id = None
    
    # Verify authentication if token provided
    if token:
        try:
            payload = auth_manager.verify_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    await manager.connect(websocket, user_id)
    await manager.subscribe_to_scan(websocket, scan_id)
    
    try:
        # Send initial scan status
        scan_result = enhanced_scanner.get_scan_result(scan_id)
        if scan_result:
            initial_message = {
                "type": WSEventType.SCAN_STATUS.value,
                "scan_id": scan_id,
                "data": {
                    "status": scan_result.status.value,
                    "progress_percent": scan_result.progress_percent,
                    "processed_urls": scan_result.processed_urls,
                    "total_urls": scan_result.total_urls,
                    "findings_count": scan_result.findings_count,
                    "checks_per_sec": scan_result.checks_per_sec,
                    "urls_per_sec": scan_result.urls_per_sec,
                    "eta_seconds": scan_result.eta_seconds
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await manager.send_to_connection(websocket, initial_message)
        
        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            metrics.websocket_message_received(message.get("type", "unknown"))
            
            message_type = message.get("type")
            
            if message_type == WSEventType.PING.value:
                # Send pong response
                pong_message = {
                    "type": WSEventType.PONG.value,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await manager.send_to_connection(websocket, pong_message)
            
            elif message_type == WSEventType.GET_SCAN_STATUS.value:
                # Send current scan status
                scan_result = enhanced_scanner.get_scan_result(scan_id)
                if scan_result:
                    status_message = {
                        "type": WSEventType.SCAN_STATUS.value,
                        "scan_id": scan_id,
                        "data": {
                            "status": scan_result.status.value,
                            "progress_percent": scan_result.progress_percent,
                            "processed_urls": scan_result.processed_urls,
                            "total_urls": scan_result.total_urls,
                            "findings_count": scan_result.findings_count,
                            "checks_per_sec": scan_result.checks_per_sec,
                            "urls_per_sec": scan_result.urls_per_sec,
                            "eta_seconds": scan_result.eta_seconds
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    await manager.send_to_connection(websocket, status_message)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket scan endpoint error", scan_id=scan_id, error=str(e))
    finally:
        manager.disconnect(websocket)


async def websocket_dashboard_endpoint(websocket: WebSocket, token: str = None):
    """WebSocket endpoint for dashboard events"""
    user_id = None
    
    # Verify authentication if token provided
    if token:
        try:
            payload = auth_manager.verify_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    await manager.connect(websocket, user_id)
    await manager.subscribe_to_dashboard(websocket)
    
    try:
        # Send initial dashboard stats with French UI support
        connection_stats = await manager.get_connection_stats()
        
        # Get provider stats for tiles
        from .results import get_provider_stats
        try:
            # Mock session for now - in real implementation use proper session
            provider_stats = {
                'aws': 0, 'sendgrid': 0, 'sparkpost': 0, 
                'twilio': 0, 'brevo': 0, 'mailgun': 0
            }
        except:
            provider_stats = {
                'aws': 0, 'sendgrid': 0, 'sparkpost': 0, 
                'twilio': 0, 'brevo': 0, 'mailgun': 0
            }
        
        scan_stats = {
            "active_scans": len(enhanced_scanner.active_scans),
            "total_findings": sum(len(findings) for findings in enhanced_scanner.findings.values()),
            "provider_hits": provider_stats,
            # French UI specific metrics
            "processed_urls": 0,
            "total_urls": 0,
            "progress_percent": 0.0,
            "urls_per_sec": 0.0,
            "https_reqs_per_sec": 0.0,
            "precision_percent": 0.0,
            "duration_seconds": 0.0,
            "eta_seconds": None
        }
        
        initial_message = {
            "type": WSEventType.DASHBOARD_STATS.value,
            "data": {
                **connection_stats,
                **scan_stats
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await manager.send_to_connection(websocket, initial_message)
        
        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            metrics.websocket_message_received(message.get("type", "unknown"))
            
            message_type = message.get("type")
            
            if message_type == WSEventType.PING.value:
                # Send pong response
                pong_message = {
                    "type": WSEventType.PONG.value,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await manager.send_to_connection(websocket, pong_message)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket dashboard endpoint error", error=str(e))
    finally:
        manager.disconnect(websocket)


# Legacy endpoint for backward compatibility
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """Legacy WebSocket endpoint"""
    # Redirect to dashboard endpoint
    await websocket_dashboard_endpoint(websocket, token)


# Utility functions for broadcasting events
async def broadcast_scan_update(scan_id: str, event_type: WSEventType, data: Dict[str, Any]):
    """Broadcast scan update to subscribers"""
    message = {
        "type": event_type.value,
        "scan_id": scan_id,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await manager.broadcast_to_scan_subscribers(scan_id, message)


async def broadcast_dashboard_update(data: Dict[str, Any]):
    """Broadcast dashboard update to subscribers"""
    message = {
        "type": WSEventType.DASHBOARD_STATS.value,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await manager.broadcast_to_dashboard_subscribers(message)


async def broadcast_scan_log(scan_id: str, log_message: str, level: str = "info"):
    """Broadcast scan log message"""
    await broadcast_scan_update(scan_id, WSEventType.SCAN_LOG, {
        "message": log_message,
        "level": level
    })


async def broadcast_scan_progress(scan_id: str, processed: int, total: int, 
                                 checks_per_sec: float = 0, urls_per_sec: float = 0,
                                 eta_seconds: Optional[int] = None):
    """Broadcast scan progress update"""
    progress_percent = (processed / total * 100) if total > 0 else 0
    
    await broadcast_scan_update(scan_id, WSEventType.SCAN_PROGRESS, {
        "processed_urls": processed,
        "total_urls": total,
        "progress_percent": round(progress_percent, 1),
        "checks_per_sec": checks_per_sec,
        "urls_per_sec": urls_per_sec,
        "eta_seconds": eta_seconds
    })


async def broadcast_scan_resources(scan_id: str, cpu_pct: float, ram_mb: float,
                                  net_mbps_in: float = 0, net_mbps_out: float = 0):
    """Broadcast scan resource usage"""
    await broadcast_scan_update(scan_id, WSEventType.SCAN_RESOURCES, {
        "cpu_pct": cpu_pct,
        "ram_mb": ram_mb,
        "net_mbps_in": net_mbps_in,
        "net_mbps_out": net_mbps_out
    })


async def broadcast_new_finding(scan_id: str, finding_data: Dict[str, Any]):
    """Broadcast new finding"""
    await broadcast_scan_update(scan_id, WSEventType.SCAN_HIT, {
        "finding": finding_data
    })


async def broadcast_scan_summary(scan_id: str, summary_data: Dict[str, Any]):
    """Broadcast scan completion summary"""
    await broadcast_scan_update(scan_id, WSEventType.SCAN_SUMMARY, summary_data)