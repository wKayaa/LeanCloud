#!/usr/bin/env python3
"""
HTTPx Scanner Web Panel
Start script for the unified scanner with web interface
"""

import uvicorn
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    # Ensure data directories exist
    os.makedirs("data/results", exist_ok=True)
    
    print("Starting HTTPx Scanner Web Panel...")
    print("Dashboard will be available at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    print("Default login: admin / admin123 (must change on first login)")
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=True
    )