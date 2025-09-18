"""Settings API endpoints for httpxCloud v1 Phase 1"""

import yaml
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
import structlog
import httpx

from ..core.models import SettingsUpdate, TelegramTestRequest, PhaseOneConfig

logger = structlog.get_logger()

router = APIRouter(prefix="/settings", tags=["settings"])

# Configuration file path
CONFIG_PATH = Path("data/config.yml")


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to load config", error=str(e))
    return {}


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to YAML file"""
    try:
        # Ensure parent directory exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info("Configuration saved", path=str(CONFIG_PATH))
        return True
    except Exception as e:
        logger.error("Failed to save config", error=str(e))
        return False


@router.get("/")
async def get_settings() -> Dict[str, Any]:
    """
    Get current settings
    
    Returns the full configuration with sensitive values masked
    """
    try:
        config = load_config()
        
        # Apply masking to sensitive values
        masked_config = config.copy()
        
        # Mask Telegram bot token
        if 'notifications' in masked_config and 'telegram' in masked_config['notifications']:
            telegram = masked_config['notifications']['telegram']
            if 'bot_token' in telegram and telegram['bot_token']:
                token = str(telegram['bot_token'])
                if len(token) > 8:
                    telegram['bot_token'] = f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
                else:
                    telegram['bot_token'] = '*' * len(token)
        
        # Mask webhook secrets
        if 'notifications' in masked_config and 'webhook_secret' in masked_config['notifications']:
            secret = masked_config['notifications']['webhook_secret']
            if secret:
                masked_config['notifications']['webhook_secret'] = '*' * len(str(secret))
        
        return {
            "config": masked_config,
            "config_path": str(CONFIG_PATH),
            "last_modified": CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None
        }
    
    except Exception as e:
        logger.error("Failed to get settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve settings: {str(e)}"
        )


@router.put("/")
async def update_settings(settings: SettingsUpdate) -> Dict[str, str]:
    """
    Update settings
    
    Partial updates are supported - only provided fields will be updated
    """
    try:
        # Load current config
        config = load_config()
        
        # Ensure required sections exist
        if 'notifications' not in config:
            config['notifications'] = {}
        
        # Update Telegram settings if provided
        if settings.telegram is not None:
            config['notifications']['telegram'] = {
                'enabled': settings.telegram.enabled,
                'bot_token': settings.telegram.bot_token,
                'chat_id': settings.telegram.chat_id
            }
            
            logger.info("Telegram settings updated", enabled=settings.telegram.enabled)
        
        # Save updated configuration
        if not save_config(config):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save configuration"
            )
        
        return {"message": "Settings updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


@router.post("/test-telegram")
async def test_telegram_settings(request: TelegramTestRequest) -> Dict[str, Any]:
    """
    Test Telegram notification settings
    
    Sends a test message using current settings
    """
    try:
        # Load current config
        config = load_config()
        
        # Get Telegram settings
        telegram_config = config.get('notifications', {}).get('telegram', {})
        
        if not telegram_config.get('enabled', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram notifications are not enabled"
            )
        
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')
        
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot token is not configured"
            )
        
        if not chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram chat ID is not configured"
            )
        
        # Send test message
        test_message = (
            "🧪 *HTTPx Cloud Test Message*\n\n"
            "This is a test message from your HTTPx Cloud scanner.\n"
            "If you received this message, your Telegram notifications are working correctly!\n\n"
            f"⏰ Sent at: {config.get('timestamp', 'unknown')}\n"
            "🚀 HTTPx Cloud v1.0"
        )
        
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                telegram_url,
                json={
                    "chat_id": chat_id,
                    "text": test_message,
                    "parse_mode": "Markdown"
                },
                timeout=10.0
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info("Telegram test message sent successfully", 
                           chat_id=chat_id, message_id=result.get('result', {}).get('message_id'))
                
                return {
                    "success": True,
                    "message": "Test message sent successfully!",
                    "chat_id": chat_id,
                    "message_id": result.get('result', {}).get('message_id'),
                    "sent_at": result.get('result', {}).get('date')
                }
            else:
                error_desc = result.get('description', 'Unknown error')
                logger.error("Telegram API returned error", error=error_desc)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Telegram API error: {error_desc}"
                )
        else:
            logger.error("Telegram API request failed", 
                        status_code=response.status_code,
                        response=response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to send message (HTTP {response.status_code})"
            )
    
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("Telegram API request timed out")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Request to Telegram API timed out"
        )
    except Exception as e:
        logger.error("Failed to test Telegram settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test Telegram settings: {str(e)}"
        )


@router.get("/defaults")
async def get_default_settings() -> Dict[str, Any]:
    """
    Get default settings structure
    
    Useful for UI to know what settings are available
    """
    try:
        default_config = {
            "scanner": {
                "adaptive_min": 10000,
                "adaptive_max": 100000
            },
            "notifications": {
                "telegram": {
                    "enabled": False,
                    "bot_token": None,
                    "chat_id": None
                },
                "slack": {
                    "enabled": False,
                    "webhook_url": None
                },
                "discord": {
                    "enabled": False,
                    "webhook_url": None
                },
                "webhooks": {
                    "enabled": False,
                    "webhook_urls": [],
                    "webhook_secret": None
                }
            },
            "validation": {
                "providers": {
                    "aws": {
                        "safe_mode": True
                    },
                    "sendgrid": {
                        "safe_mode": True
                    }
                }
            },
            "exports": {
                "mask_by_default": True
            },
            "retention": {
                "scans_days": 30,
                "logs_days": 90
            },
            "ui": {
                "theme": {
                    "name": "futuristic",
                    "dark_mode": True
                }
            }
        }
        
        return {
            "defaults": default_config,
            "description": "Default configuration structure for HTTPx Cloud v1"
        }
    
    except Exception as e:
        logger.error("Failed to get default settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default settings: {str(e)}"
        )


@router.post("/reset")
async def reset_settings_to_defaults() -> Dict[str, str]:
    """
    Reset all settings to defaults
    
    WARNING: This will overwrite all current settings
    """
    try:
        # Get default settings
        defaults_response = await get_default_settings()
        default_config = defaults_response["defaults"]
        
        # Save defaults as current config
        if not save_config(default_config):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save default configuration"
            )
        
        logger.info("Settings reset to defaults")
        
        return {
            "message": "Settings have been reset to defaults",
            "warning": "All previous settings have been overwritten"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset settings", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset settings: {str(e)}"
        )