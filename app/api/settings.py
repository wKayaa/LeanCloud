"""
Settings API endpoints for system configuration
Implements Telegram settings and notification testing
"""

import os
import json
import httpx
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import structlog

from ..core.auth import get_current_user
from ..core.models import TelegramSettings

logger = structlog.get_logger()

router = APIRouter()

# Settings file path
SETTINGS_FILE = Path("data/settings.json")
SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_settings() -> Dict[str, Any]:
    """Load settings from file"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load settings file", error=str(e))
    return {}


def _save_settings(settings: Dict[str, Any]) -> None:
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logger.error("Failed to save settings", error=str(e))
        raise


def _mask_token(token: str) -> str:
    """Mask sensitive token for display"""
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


@router.post("/settings/telegram")
async def save_telegram_settings(
    telegram_settings: TelegramSettings,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Save Telegram notification settings"""
    try:
        # Load existing settings
        settings = _load_settings()
        
        # Update Telegram settings
        settings['telegram'] = {
            'bot_token': telegram_settings.bot_token,
            'chat_id': telegram_settings.chat_id,
            'enabled': telegram_settings.enabled
        }
        
        # Save to file
        _save_settings(settings)
        
        logger.info("Telegram settings saved", 
                   user=current_user.get('sub'),
                   chat_id=telegram_settings.chat_id)
        
        return {
            "message": "Telegram settings saved successfully",
            "settings": {
                "bot_token": _mask_token(telegram_settings.bot_token),
                "chat_id": telegram_settings.chat_id,
                "enabled": telegram_settings.enabled
            }
        }
        
    except Exception as e:
        logger.error("Failed to save Telegram settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/telegram")
async def get_telegram_settings(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current Telegram settings (masked)"""
    try:
        settings = _load_settings()
        telegram_settings = settings.get('telegram', {})
        
        if not telegram_settings:
            return {
                "bot_token": "",
                "chat_id": "",
                "enabled": False
            }
        
        return {
            "bot_token": _mask_token(telegram_settings.get('bot_token', '')),
            "chat_id": telegram_settings.get('chat_id', ''),
            "enabled": telegram_settings.get('enabled', False)
        }
        
    except Exception as e:
        logger.error("Failed to get Telegram settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/test/telegram")
async def test_telegram_notification(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test Telegram notification"""
    try:
        # Load Telegram settings
        settings = _load_settings()
        telegram_settings = settings.get('telegram', {})
        
        if not telegram_settings or not telegram_settings.get('enabled'):
            raise HTTPException(status_code=400, detail="Telegram notifications not configured or disabled")
        
        bot_token = telegram_settings.get('bot_token')
        chat_id = telegram_settings.get('chat_id')
        
        if not bot_token or not chat_id:
            raise HTTPException(status_code=400, detail="Bot token or chat ID not configured")
        
        # Prepare test message
        test_message = f"""🚀 HTTPx Cloud Scanner - Test Notification

✅ System Status: Online
👤 User: {current_user.get('sub', 'Unknown')}
🕐 Time: {str(datetime.now())}

This is a test notification to verify Telegram integration is working correctly.

🎯 Your notifications are configured and ready!"""
        
        # Send test message via Telegram API
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                telegram_url,
                json={
                    "chat_id": chat_id,
                    "text": test_message,
                    "parse_mode": "HTML"
                }
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info("Telegram test notification sent successfully",
                           user=current_user.get('sub'),
                           chat_id=chat_id)
                return {
                    "success": True,
                    "message": "Test notification sent successfully!",
                    "telegram_response": "Message delivered"
                }
            else:
                error_desc = result.get('description', 'Unknown error')
                logger.error("Telegram API error", error=error_desc)
                raise HTTPException(status_code=400, detail=f"Telegram API error: {error_desc}")
        else:
            logger.error("Telegram HTTP error", status_code=response.status_code)
            raise HTTPException(status_code=400, detail=f"HTTP error: {response.status_code}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send test notification", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_all_settings(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all system settings (masked sensitive fields)"""
    try:
        settings = _load_settings()
        
        # Mask sensitive data
        if 'telegram' in settings and 'bot_token' in settings['telegram']:
            settings['telegram']['bot_token'] = _mask_token(settings['telegram']['bot_token'])
        
        return settings
        
    except Exception as e:
        logger.error("Failed to get settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/scan_defaults")
async def save_scan_defaults(
    defaults: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Save scan default settings"""
    try:
        # Validate inputs
        concurrency = defaults.get('concurrency', 1000)
        timeout = defaults.get('timeout', 10)
        
        if not isinstance(concurrency, int) or concurrency < 10 or concurrency > 50000:
            raise HTTPException(status_code=400, detail="Concurrency must be between 10 and 50,000")
        
        if not isinstance(timeout, int) or timeout < 1 or timeout > 60:
            raise HTTPException(status_code=400, detail="Timeout must be between 1 and 60 seconds")
        
        # Load and update settings
        settings = _load_settings()
        settings['scan_defaults'] = {
            'concurrency': concurrency,
            'timeout': timeout
        }
        
        _save_settings(settings)
        
        logger.info("Scan defaults saved", 
                   user=current_user.get('sub'),
                   concurrency=concurrency,
                   timeout=timeout)
        
        return {
            "message": "Scan defaults saved successfully",
            "settings": settings['scan_defaults']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save scan defaults", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/data_retention")
async def save_data_retention(
    retention: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Save data retention settings"""
    try:
        # Validate inputs
        scan_retention = retention.get('scan_retention_days', 30)
        hit_retention = retention.get('hit_retention_days', 90)
        
        if not isinstance(scan_retention, int) or scan_retention < 1 or scan_retention > 365:
            raise HTTPException(status_code=400, detail="Scan retention must be between 1 and 365 days")
        
        if not isinstance(hit_retention, int) or hit_retention < 1 or hit_retention > 365:
            raise HTTPException(status_code=400, detail="Hit retention must be between 1 and 365 days")
        
        # Load and update settings
        settings = _load_settings()
        settings['data_retention'] = {
            'scan_retention_days': scan_retention,
            'hit_retention_days': hit_retention
        }
        
        _save_settings(settings)
        
        logger.info("Data retention settings saved", 
                   user=current_user.get('sub'),
                   scan_retention=scan_retention,
                   hit_retention=hit_retention)
        
        return {
            "message": "Data retention settings saved successfully",
            "settings": settings['data_retention']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save data retention settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))