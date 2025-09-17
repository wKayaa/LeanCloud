from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from typing import Dict, List
from datetime import datetime

from ..core.scanner import scanner
from ..core.auth import auth_manager


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.scan_subscribers: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from scan subscribers
        for scan_id in list(self.scan_subscribers.keys()):
            if websocket in self.scan_subscribers[scan_id]:
                self.scan_subscribers[scan_id].remove(websocket)
                if not self.scan_subscribers[scan_id]:
                    del self.scan_subscribers[scan_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to_scan_subscribers(self, scan_id: str, message: str):
        if scan_id not in self.scan_subscribers:
            return
        
        disconnected = []
        for connection in self.scan_subscribers[scan_id]:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            if conn in self.scan_subscribers[scan_id]:
                self.scan_subscribers[scan_id].remove(conn)
        
        if not self.scan_subscribers[scan_id]:
            del self.scan_subscribers[scan_id]
    
    def subscribe_to_scan(self, scan_id: str, websocket: WebSocket):
        if scan_id not in self.scan_subscribers:
            self.scan_subscribers[scan_id] = []
        self.scan_subscribers[scan_id].append(websocket)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """WebSocket endpoint for real-time updates"""
    # Verify authentication
    if token:
        try:
            payload = auth_manager.verify_token(token)
        except:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "subscribe_scan":
                scan_id = message.get("scan_id")
                if scan_id:
                    manager.subscribe_to_scan(scan_id, websocket)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscribed",
                            "scan_id": scan_id,
                            "timestamp": datetime.now().isoformat()
                        }),
                        websocket
                    )
            
            elif message_type == "get_scan_status":
                scan_id = message.get("scan_id")
                if scan_id:
                    scan_result = scanner.get_scan_result(scan_id)
                    if scan_result:
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "scan_status",
                                "scan_id": scan_id,
                                "status": scan_result.status.value,
                                "processed_urls": scan_result.processed_urls,
                                "total_urls": scan_result.total_urls,
                                "findings_count": scan_result.findings_count,
                                "timestamp": datetime.now().isoformat()
                            }),
                            websocket
                        )
            
            elif message_type == "ping":
                await manager.send_personal_message(
                    json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }),
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_scan_update(scan_id: str, update_type: str, data: dict = None):
    """Broadcast scan updates to subscribers"""
    message = {
        "type": update_type,
        "scan_id": scan_id,
        "timestamp": datetime.now().isoformat()
    }
    
    if data:
        message.update(data)
    
    await manager.send_to_scan_subscribers(scan_id, json.dumps(message))


async def broadcast_scan_log(scan_id: str, log_message: str):
    """Broadcast scan log message to subscribers"""
    await broadcast_scan_update(scan_id, "scan_log", {"message": log_message})


async def broadcast_scan_progress(scan_id: str, processed: int, total: int):
    """Broadcast scan progress to subscribers"""
    await broadcast_scan_update(scan_id, "scan_progress", {
        "processed_urls": processed,
        "total_urls": total,
        "progress_percent": round((processed / total) * 100, 1) if total > 0 else 0
    })


async def broadcast_new_finding(scan_id: str, finding_data: dict):
    """Broadcast new finding to subscribers"""
    await broadcast_scan_update(scan_id, "new_finding", {"finding": finding_data})