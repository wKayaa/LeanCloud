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
import asyncio
import structlog

from .api.endpoints import router as legacy_api_router
from .api.endpoints_enhanced import router as api_router
from .api.websocket_enhanced import websocket_scan_endpoint, websocket_dashboard_endpoint, websocket_endpoint
from .core.config import config_manager
from .core.database import init_database, cleanup_database
from .core.redis_manager import init_redis, close_redis
from .core.scanner_enhanced import enhanced_scanner
from .core.notifications import notification_manager
from .core.metrics import metrics

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="HTTPx Cloud Scanner v1",
    description="Production-ready HTTP response scanner with real-time telemetry and high concurrency",
    version="1.0.0",
    openapi_url="/api/openapi.json"
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


# Enhanced rate limiting middleware
class EnhancedRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}
        self.redis_available = False
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/healthz", "/metrics"]:
            return await call_next(request)
        
        try:
            # Try to use Redis for distributed rate limiting
            if not self.redis_available:
                from .core.redis_manager import get_redis
                redis = get_redis()
                self.redis_available = True
            
            # Use Redis-based rate limiting
            rate_limit_key = f"rate_limit:{client_ip}"
            allowed = await redis.rate_limit(rate_limit_key, self.calls, self.period)
            
            if not allowed:
                return Response("Rate limit exceeded", status_code=429)
                
        except Exception:
            # Fall back to in-memory rate limiting
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


# Add enhanced rate limiting
config = config_manager.get_config()
app.add_middleware(
    EnhancedRateLimitMiddleware,
    calls=config.rate_limit_per_minute,
    period=60
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["v1"])
app.include_router(legacy_api_router, prefix="/api/v1", tags=["legacy"])  # Backward compatibility

# Enhanced WebSocket endpoints
@app.websocket("/ws")
async def websocket_main(websocket: WebSocket, token: str = None):
    """Main WebSocket endpoint (backward compatibility)"""
    await websocket_endpoint(websocket, token)

@app.websocket("/ws/scans/{scan_id}")
async def websocket_scan(websocket: WebSocket, scan_id: str, token: str = None):
    """Scan-specific WebSocket endpoint"""
    await websocket_scan_endpoint(websocket, scan_id, token)

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str = None):
    """Dashboard WebSocket endpoint"""
    await websocket_dashboard_endpoint(websocket, token)

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Serve enhanced UI
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the enhanced UI"""
    ui_file = Path(__file__).parent / "static" / "index.html"
    if ui_file.exists():
        return HTMLResponse(content=ui_file.read_text(), status_code=200)
    else:
        # Return a placeholder if UI file doesn't exist yet
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HTTPx Cloud Scanner v1</title>
            <style>
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                    background: linear-gradient(135deg, #0B0B12 0%, #1a1a2e 100%);
                    color: #e2e8f0;
                    margin: 0;
                    padding: 2rem;
                    min-height: 100vh;
                }
                .container { max-width: 800px; margin: 0 auto; text-align: center; }
                h1 { 
                    background: linear-gradient(45deg, #7C3AED, #22D3EE);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }
                .status { color: #34D399; font-size: 1.2rem; margin-bottom: 2rem; }
                .features { text-align: left; margin: 2rem 0; }
                .feature { margin: 1rem 0; }
                a { color: #22D3EE; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>HTTPx Cloud Scanner v1</h1>
                <div class="status">✅ Backend services are online</div>
                <div class="features">
                    <div class="feature">🚀 High-concurrency scanning (up to 50k async tasks)</div>
                    <div class="feature">📊 Real-time telemetry and WebSocket streaming</div>
                    <div class="feature">🔍 Advanced service validation (AWS, SendGrid, Docker, K8s)</div>
                    <div class="feature">📱 Telegram, Slack, Discord notifications</div>
                    <div class="feature">📈 Prometheus metrics and monitoring</div>
                    <div class="feature">🎯 Enhanced hit detection with confidence scoring</div>
                </div>
                <p>Web interface is being set up...</p>
                <p>API is available at <a href="/docs">/docs</a></p>
                <p>Metrics at <a href="/api/v1/metrics">/api/v1/metrics</a></p>
            </div>
        </body>
        </html>
        """, status_code=200)


# Health check
@app.get("/health")
@app.get("/healthz")
async def health():
    """Enhanced health check"""
    return {
        "status": "healthy",
        "service": "httpx_cloud_scanner",
        "version": "1.0.0",
        "features": {
            "high_concurrency": True,
            "real_time_telemetry": True,
            "notifications": True,
            "prometheus_metrics": True,
            "advanced_validation": True
        },
        "timestamp": time.time()
    }


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting HTTPx Cloud Scanner v1...")
    
    try:
        config = config_manager.get_config()
        
        # Validate configuration
        issues = config_manager.validate_config()
        if issues:
            logger.warning("Configuration issues detected", issues=issues)
        
        # Initialize database
        try:
            await init_database(config_manager.get_database_url())
            logger.info("Database initialized")
        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            # Continue with in-memory fallback
        
        # Initialize Redis
        try:
            await init_redis(config_manager.get_redis_url())
            logger.info("Redis initialized")
        except Exception as e:
            logger.error("Redis initialization failed", error=str(e))
            # Continue without Redis (degraded mode)
        
        # Initialize enhanced scanner
        await enhanced_scanner.initialize()
        logger.info("Enhanced scanner initialized")
        
        # Initialize notification manager
        await notification_manager.initialize()
        logger.info("Notification manager initialized")
        
        # Update service info metric
        metrics.service_info.info({
            'version': '1.0.0',
            'component': 'httpx_cloud_scanner',
            'high_concurrency': 'true',
            'max_concurrency': str(config.max_concurrency)
        })
        
        logger.info("HTTPx Cloud Scanner v1 started successfully",
                   max_concurrency=config.max_concurrency,
                   adaptive_concurrency=config.adaptive_concurrency,
                   backpressure_enabled=config.enable_backpressure)
        
    except Exception as e:
        logger.error("Startup failed", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down HTTPx Cloud Scanner v1...")
    
    try:
        # Close enhanced scanner
        await enhanced_scanner.close()
        logger.info("Enhanced scanner closed")
        
        # Close notification manager
        await notification_manager.close()
        logger.info("Notification manager closed")
        
        # Close Redis
        await close_redis()
        logger.info("Redis connection closed")
        
        # Close database
        await cleanup_database()
        logger.info("Database connection closed")
        
        logger.info("HTTPx Cloud Scanner v1 shutdown complete")
        
    except Exception as e:
        logger.error("Shutdown error", error=str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Production-grade server configuration
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,  # Single worker for WebSocket state consistency
        loop="uvloop",
        http="httptools",
        log_level="info",
        access_log=True,
        server_header=False,
        date_header=False
    )