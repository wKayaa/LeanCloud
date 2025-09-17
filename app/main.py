from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging
from pathlib import Path

from .api.endpoints import router as api_router
from .api.websocket import websocket_endpoint
from .core.config import config_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="HTTPx Scanner",
    description="Production-ready HTTP response scanner with web panel",
    version="1.0.0"
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()
        
        # Clean old entries
        self.clients = {
            ip: times for ip, times in self.clients.items()
            if any(t > now - self.period for t in times)
        }
        
        # Check rate limit
        client_calls = self.clients.get(client_ip, [])
        recent_calls = [t for t in client_calls if t > now - self.period]
        
        if len(recent_calls) >= self.calls:
            return Response("Rate limit exceeded", status_code=429)
        
        # Record this call
        recent_calls.append(now)
        self.clients[client_ip] = recent_calls
        
        response = await call_next(request)
        return response


# Add rate limiting
config = config_manager.get_config()
app.add_middleware(
    RateLimitMiddleware,
    calls=config.rate_limit_per_minute,
    period=60
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket, token: str = None):
    await websocket_endpoint(websocket, token)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Serve main UI
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main UI"""
    ui_file = Path(__file__).parent / "static" / "index.html"
    if ui_file.exists():
        return HTMLResponse(content=ui_file.read_text(), status_code=200)
    else:
        # Return a simple placeholder if UI file doesn't exist yet
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HTTPx Scanner</title>
        </head>
        <body>
            <h1>HTTPx Scanner</h1>
            <p>Web interface is being set up...</p>
            <p>API is available at <a href="/docs">/docs</a></p>
        </body>
        </html>
        """, status_code=200)


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "httpx_scanner"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)