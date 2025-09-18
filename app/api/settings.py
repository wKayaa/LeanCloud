"""Settings API endpoints for Telegram and other configurations"""

import requests
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import json
from datetime import datetime

from ..core.auth import get_current_user, require_admin
from ..core.models import TelegramSettings
from ..core.config import config_manager

router = APIRouter()

# In-memory settings storage (replace with database in production)
settings_storage: Dict[str, Any] = {
    "telegram": {
        "bot_token": None,
        "chat_id": None,
        "enabled": False
    }
}


@router.post("/settings/telegram")
async def save_telegram_settings(
    settings: TelegramSettings,
    current_user: Dict = Depends(require_admin)
) -> Dict[str, Any]:
    """Save Telegram settings"""
    
    # Validate bot token format (basic check)
    if not settings.bot_token.startswith(("bot", "")) or ":" not in settings.bot_token:
        raise HTTPException(
            status_code=400, 
            detail="Invalid Telegram bot token format"
        )
    
    # Store settings (mask the token in response)
    settings_storage["telegram"] = {
        "bot_token": settings.bot_token,
        "chat_id": settings.chat_id,
        "enabled": settings.enabled
    }
    
    # Update config manager
    config = config_manager.get_config()
    config.telegram_bot_token = settings.bot_token
    config.telegram_chat_id = settings.chat_id
    config_manager.save_config(config)
    
    return {
        "message": "Telegram settings saved successfully",
        "settings": {
            "bot_token": f"***{settings.bot_token[-6:]}" if settings.bot_token else None,
            "chat_id": settings.chat_id,
            "enabled": settings.enabled
        }
    }


@router.get("/settings/telegram")
async def get_telegram_settings(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current Telegram settings (masked)"""
    
    telegram_settings = settings_storage.get("telegram", {})
    
    return {
        "bot_token": f"***{telegram_settings.get('bot_token', '')[-6:]}" if telegram_settings.get('bot_token') else None,
        "chat_id": telegram_settings.get("chat_id"),
        "enabled": telegram_settings.get("enabled", False)
    }


@router.post("/notifications/test/telegram")
async def test_telegram_notification(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test Telegram notification"""
    
    telegram_settings = settings_storage.get("telegram", {})
    
    if not telegram_settings.get("enabled"):
        raise HTTPException(
            status_code=400,
            detail="Telegram notifications are not enabled"
        )
    
    bot_token = telegram_settings.get("bot_token")
    chat_id = telegram_settings.get("chat_id")
    
    if not bot_token or not chat_id:
        raise HTTPException(
            status_code=400,
            detail="Telegram bot token and chat ID must be configured"
        )
    
    # Send test message
    try:
        success = await _send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            message="🧪 Test notification from HTTPx Cloud Scanner\n\n✅ Telegram integration is working correctly!"
        )
        
        if success:
            return {
                "message": "Test notification sent successfully",
                "status": "success"
            }
        else:
            return {
                "message": "Failed to send test notification",
                "status": "error"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send Telegram notification: {str(e)}"
        )


@router.get("/settings")
async def get_all_settings(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all application settings (masked sensitive values)"""
    
    config = config_manager.get_config()
    
    return {
        "telegram": {
            "bot_token": f"***{config.telegram_bot_token[-6:]}" if config.telegram_bot_token else None,
            "chat_id": config.telegram_chat_id,
            "enabled": bool(config.telegram_bot_token and config.telegram_chat_id)
        },
        "scanning": {
            "max_concurrency": config.max_concurrency,
            "rate_limit_per_minute": config.rate_limit_per_minute,
            "httpx_path": config.httpx_path
        },
        "security": {
            "auth_required": config.auth_required,
            "first_run": config.first_run
        }
    }


@router.put("/settings")
async def update_settings(
    settings: Dict[str, Any],
    current_user: Dict = Depends(require_admin)
) -> Dict[str, str]:
    """Update multiple settings at once"""
    
    config = config_manager.get_config()
    
    # Update scanning settings
    if "scanning" in settings:
        scanning = settings["scanning"]
        if "max_concurrency" in scanning:
            config.max_concurrency = scanning["max_concurrency"]
        if "rate_limit_per_minute" in scanning:
            config.rate_limit_per_minute = scanning["rate_limit_per_minute"]
        if "httpx_path" in scanning:
            config.httpx_path = scanning["httpx_path"]
    
    # Update security settings
    if "security" in settings:
        security = settings["security"]
        if "auth_required" in security:
            config.auth_required = security["auth_required"]
    
    # Save updated config
    config_manager.save_config(config)
    
    return {
        "message": "Settings updated successfully",
        "status": "success"
    }


async def _send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


# Helper function to send scan notifications
async def send_scan_notification(scan_id: str, status: str, hits_count: int = 0):
    """Send scan status notification via Telegram"""
    
    telegram_settings = settings_storage.get("telegram", {})
    
    if not telegram_settings.get("enabled"):
        return
    
    bot_token = telegram_settings.get("bot_token")
    chat_id = telegram_settings.get("chat_id")
    
    if not bot_token or not chat_id:
        return
    
    # Create notification message
    status_emoji = {
        "started": "🚀",
        "completed": "✅", 
        "failed": "❌",
        "stopped": "⏹️"
    }
    
    emoji = status_emoji.get(status, "ℹ️")
    
    message = f"{emoji} *Scan {scan_id[:8]}* - {status.upper()}"
    
    if hits_count > 0:
        message += f"\n🎯 *{hits_count}* hits found"
    
    message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await _send_telegram_message(bot_token, chat_id, message)