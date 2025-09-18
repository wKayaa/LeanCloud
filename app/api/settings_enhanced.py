"""Enhanced settings API endpoints for httpxCloud v1"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import structlog
import requests

from ..core.auth import get_current_user, require_admin
from ..core.models import TelegramSettings

logger = structlog.get_logger()

router = APIRouter()

# Global settings storage (in production, this would be in database)
telegram_settings = TelegramSettings()


@router.post("/settings/telegram")
async def save_telegram_settings(
    settings: TelegramSettings,
    current_user = Depends(require_admin)
) -> Dict[str, str]:
    """Save Telegram notification settings"""
    
    try:
        global telegram_settings
        
        # Validate bot token format if provided
        if settings.bot_token and not settings.bot_token.startswith('bot'):
            if ':' not in settings.bot_token:
                raise HTTPException(status_code=400, detail="Invalid bot token format")
        
        # Validate chat ID format if provided
        if settings.chat_id and not (settings.chat_id.startswith('-') or settings.chat_id.isdigit() or settings.chat_id.startswith('@')):
            raise HTTPException(status_code=400, detail="Invalid chat ID format")
        
        # Store settings (mask token in logs)
        telegram_settings = settings
        
        logger.info("Telegram settings updated by admin", 
                   admin=current_user.get("username"),
                   chat_id=settings.chat_id,
                   enabled=settings.enabled)
        
        return {
            "message": "Telegram settings saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save Telegram settings", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save settings")


@router.get("/settings/telegram")
async def get_telegram_settings(
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get Telegram settings (masked for security)"""
    
    return {
        "bot_token": "***MASKED***" if telegram_settings.bot_token else None,
        "chat_id": telegram_settings.chat_id,
        "enabled": telegram_settings.enabled
    }


@router.post("/notifications/test/telegram")
async def test_telegram_notification(
    current_user = Depends(require_admin)
) -> Dict[str, str]:
    """Send a test Telegram notification"""
    
    if not telegram_settings.bot_token or not telegram_settings.chat_id:
        raise HTTPException(status_code=400, detail="Telegram settings not configured")
    
    try:
        # Prepare test message
        test_message = f"""🚀 HTTPx Cloud Scanner - Test Notification

👤 Admin: {current_user.get("username")}
⏰ Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}
📊 Status: All systems operational

This is a test message to verify your Telegram integration is working correctly."""
        
        # Send via Telegram Bot API
        bot_token = telegram_settings.bot_token
        if bot_token.startswith('bot'):
            bot_token = bot_token[3:]  # Remove 'bot' prefix if present
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": telegram_settings.chat_id,
            "text": test_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        # Use asyncio to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: requests.post(url, json=payload, timeout=10)
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info("Test Telegram notification sent successfully", 
                           admin=current_user.get("username"),
                           chat_id=telegram_settings.chat_id)
                return {
                    "message": "Test notification sent successfully to Telegram"
                }
            else:
                error_msg = result.get("description", "Unknown Telegram API error")
                logger.error("Telegram API error", error=error_msg)
                raise HTTPException(status_code=400, detail=f"Telegram API error: {error_msg}")
        else:
            logger.error("Telegram request failed", status_code=response.status_code, response=response.text)
            raise HTTPException(status_code=400, detail=f"Telegram request failed: {response.status_code}")
    
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Telegram request timed out")
    except requests.exceptions.RequestException as e:
        logger.error("Telegram request error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Failed to send Telegram message: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send test Telegram notification", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send test notification")


# Helper function to send notifications (can be called from other modules)
async def send_telegram_notification(message: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram notification message"""
    
    if not telegram_settings.enabled or not telegram_settings.bot_token or not telegram_settings.chat_id:
        return False
    
    try:
        bot_token = telegram_settings.bot_token
        if bot_token.startswith('bot'):
            bot_token = bot_token[3:]
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": telegram_settings.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, json=payload, timeout=10)
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("ok", False)
        
        return False
        
    except Exception as e:
        logger.error("Failed to send Telegram notification", error=str(e))
        return False