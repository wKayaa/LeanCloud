"""Notification system for Telegram, Slack, Discord, and webhooks"""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx
import structlog

from .models import Finding, ScanResult, NotificationConfig
from .config import config_manager

logger = structlog.get_logger()


class NotificationManager:
    """Manages all notification channels"""
    
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
        
    async def initialize(self):
        """Initialize notification manager"""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10)
        )
        logger.info("Notification manager initialized")
    
    async def close(self):
        """Close notification manager"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Notification manager closed")
    
    async def send_scan_started(self, scan_result: ScanResult):
        """Send scan started notification"""
        config = config_manager.get_config()
        notification_config = self._get_notification_config()
        
        message = self._format_scan_started_message(scan_result)
        
        # Send to all enabled channels
        tasks = []
        
        if notification_config.telegram_enabled:
            tasks.append(self._send_telegram(message, notification_config))
        
        if notification_config.slack_enabled:
            tasks.append(self._send_slack(message, notification_config))
        
        if notification_config.discord_enabled:
            tasks.append(self._send_discord(message, notification_config))
        
        if notification_config.webhooks_enabled:
            webhook_data = {
                "event": "scan.started",
                "scan_id": scan_result.id,
                "crack_id": scan_result.crack_id,
                "data": {
                    "targets": scan_result.targets,
                    "concurrency": scan_result.config.concurrency,
                    "started_at": scan_result.started_at.isoformat() if scan_result.started_at else None
                }
            }
            for webhook_url in notification_config.webhook_urls:
                tasks.append(self._send_webhook(webhook_url, webhook_data, notification_config))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_scan_completed(self, scan_result: ScanResult):
        """Send scan completed notification"""
        notification_config = self._get_notification_config()
        
        message = self._format_scan_completed_message(scan_result)
        
        # Send to all enabled channels
        tasks = []
        
        if notification_config.telegram_enabled:
            tasks.append(self._send_telegram(message, notification_config))
        
        if notification_config.slack_enabled:
            tasks.append(self._send_slack(message, notification_config))
        
        if notification_config.discord_enabled:
            tasks.append(self._send_discord(message, notification_config))
        
        if notification_config.webhooks_enabled:
            webhook_data = {
                "event": "scan.completed",
                "scan_id": scan_result.id,
                "crack_id": scan_result.crack_id,
                "data": {
                    "status": scan_result.status.value,
                    "findings_count": scan_result.findings_count,
                    "hits_count": scan_result.hits_count,
                    "docker_infected": scan_result.docker_infected,
                    "k8s_infected": scan_result.k8s_infected,
                    "completed_at": scan_result.completed_at.isoformat() if scan_result.completed_at else None
                }
            }
            for webhook_url in notification_config.webhook_urls:
                tasks.append(self._send_webhook(webhook_url, webhook_data, notification_config))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_finding_alert(self, finding: Finding):
        """Send finding alert notification"""
        notification_config = self._get_notification_config()
        
        message = self._format_finding_message(finding)
        
        # Send to all enabled channels
        tasks = []
        
        if notification_config.telegram_enabled:
            tasks.append(self._send_telegram(message, notification_config))
        
        if notification_config.slack_enabled:
            tasks.append(self._send_slack_finding(finding, notification_config))
        
        if notification_config.discord_enabled:
            tasks.append(self._send_discord_finding(finding, notification_config))
        
        if notification_config.webhooks_enabled:
            webhook_data = {
                "event": "scan.hit",
                "scan_id": finding.scan_id,
                "crack_id": finding.crack_id,
                "data": {
                    "hit_id": finding.id,
                    "service": finding.service,
                    "works": finding.works,
                    "confidence": finding.confidence,
                    "severity": finding.severity,
                    "source_url": finding.source_url,
                    "regions": finding.regions,
                    "capabilities": finding.capabilities,
                    "masked": True,  # Always mask in webhooks by default
                    "evidence_masked": finding.evidence_masked,
                    "created_at": finding.created_at.isoformat()
                }
            }
            for webhook_url in notification_config.webhook_urls:
                tasks.append(self._send_webhook(webhook_url, webhook_data, notification_config))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _get_notification_config(self) -> NotificationConfig:
        """Get notification configuration"""
        config = config_manager.get_config()
        
        return NotificationConfig(
            telegram_enabled=bool(config.telegram_bot_token and config.telegram_chat_id),
            telegram_bot_token=config.telegram_bot_token,
            telegram_chat_id=config.telegram_chat_id,
            slack_enabled=bool(config.slack_webhook_url),
            slack_webhook_url=config.slack_webhook_url,
            discord_enabled=bool(config.discord_webhook_url),
            discord_webhook_url=config.discord_webhook_url,
            webhooks_enabled=bool(config.discord_webhook_url),  # TODO: Fix this
            webhook_urls=[],  # TODO: Implement webhook URLs list
            webhook_secret=config.webhook_secret
        )
    
    def _format_scan_started_message(self, scan_result: ScanResult) -> str:
        """Format scan started message"""
        return f"""🚀 **HTTPx Scan Started**

**Crack ID:** #{scan_result.crack_id}
**Targets:** {len(scan_result.targets)}
**Concurrency:** {scan_result.config.concurrency} threads
**Total URLs:** {scan_result.total_urls:,}
**Started:** {scan_result.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if scan_result.started_at else 'N/A'}

_Scanning in progress..._"""
    
    def _format_scan_completed_message(self, scan_result: ScanResult) -> str:
        """Format scan completed message"""
        duration = ""
        if scan_result.started_at and scan_result.completed_at:
            delta = scan_result.completed_at - scan_result.started_at
            duration = f"\n**Duration:** {delta.total_seconds():.0f}s"
        
        infected_summary = ""
        if scan_result.docker_infected > 0 or scan_result.k8s_infected > 0:
            infected_summary = f"\n🚨 **Infected Systems:**\n"
            if scan_result.docker_infected > 0:
                infected_summary += f"• Docker Containers: {scan_result.docker_infected}\n"
            if scan_result.k8s_infected > 0:
                infected_summary += f"• K8s Pods: {scan_result.k8s_infected}\n"
        
        status_emoji = {
            "completed": "✅",
            "failed": "❌", 
            "stopped": "⏹️"
        }.get(scan_result.status.value, "ℹ️")
        
        return f"""{status_emoji} **HTTPx Scan {scan_result.status.value.title()}**

**Crack ID:** #{scan_result.crack_id}
**Status:** {scan_result.status.value.upper()}
**Findings:** {scan_result.findings_count}
**Hits:** {scan_result.hits_count}
**URLs Processed:** {scan_result.processed_urls:,}/{scan_result.total_urls:,}{duration}{infected_summary}

**Completed:** {scan_result.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if scan_result.completed_at else 'N/A'}"""
    
    def _format_finding_message(self, finding: Finding) -> str:
        """Format finding message for Telegram"""
        works_status = "✅ **WORKS**" if finding.works else "❓ Unverified"
        confidence_bar = "🟩" * int(finding.confidence * 5) + "⬜" * (5 - int(finding.confidence * 5))
        
        regions_text = ""
        if finding.regions:
            regions_text = f"\n**Regions:** {', '.join(finding.regions)}"
        
        capabilities_text = ""
        if finding.capabilities:
            capabilities_text = f"\n**Access:** {', '.join(finding.capabilities[:3])}"
            if len(finding.capabilities) > 3:
                capabilities_text += f" (+{len(finding.capabilities) - 3} more)"
        
        return f"""🎯 **New {finding.service.upper()} Hit** (#{finding.crack_id})

**Evidence:** `{finding.evidence_masked}`
**Status:** {works_status}
**Confidence:** {confidence_bar} ({finding.confidence:.1%})
**URL:** {finding.source_url}{regions_text}{capabilities_text}

**Crack ID:** #{finding.crack_id}
**Severity:** {finding.severity.upper()}
**Found:** {finding.created_at.strftime('%H:%M:%S UTC')}"""
    
    async def _send_telegram(self, message: str, config: NotificationConfig):
        """Send Telegram notification"""
        try:
            url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
            
            payload = {
                "chat_id": config.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            
            logger.info("Telegram notification sent")
            
        except Exception as e:
            logger.error("Failed to send Telegram notification", error=str(e))
    
    async def _send_slack(self, message: str, config: NotificationConfig):
        """Send Slack notification"""
        try:
            payload = {
                "text": message,
                "username": "HTTPx Scanner",
                "icon_emoji": ":mag:",
                "unfurl_links": False
            }
            
            response = await self.http_client.post(config.slack_webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Slack notification sent")
            
        except Exception as e:
            logger.error("Failed to send Slack notification", error=str(e))
    
    async def _send_slack_finding(self, finding: Finding, config: NotificationConfig):
        """Send Slack finding with rich formatting"""
        try:
            color = {
                "critical": "#FF0000",
                "high": "#FF6600", 
                "medium": "#FFAA00",
                "low": "#00AA00"
            }.get(finding.severity, "#808080")
            
            works_text = "✅ VERIFIED" if finding.works else "❓ Unverified"
            
            fields = [
                {"title": "Service", "value": finding.service.upper(), "short": True},
                {"title": "Status", "value": works_text, "short": True},
                {"title": "Confidence", "value": f"{finding.confidence:.1%}", "short": True},
                {"title": "Severity", "value": finding.severity.upper(), "short": True}
            ]
            
            if finding.regions:
                fields.append({"title": "Regions", "value": ", ".join(finding.regions), "short": False})
            
            if finding.capabilities:
                capabilities = ", ".join(finding.capabilities[:5])
                if len(finding.capabilities) > 5:
                    capabilities += f" (+{len(finding.capabilities) - 5} more)"
                fields.append({"title": "Capabilities", "value": capabilities, "short": False})
            
            attachment = {
                "color": color,
                "title": f"New {finding.service.upper()} Hit",
                "title_link": finding.source_url,
                "fields": fields,
                "footer": f"Crack ID: #{finding.crack_id}",
                "ts": int(finding.created_at.timestamp())
            }
            
            payload = {
                "text": f"🎯 New finding discovered!",
                "attachments": [attachment],
                "username": "HTTPx Scanner",
                "icon_emoji": ":mag:"
            }
            
            response = await self.http_client.post(config.slack_webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Slack finding notification sent")
            
        except Exception as e:
            logger.error("Failed to send Slack finding notification", error=str(e))
    
    async def _send_discord(self, message: str, config: NotificationConfig):
        """Send Discord notification"""
        try:
            payload = {
                "content": message,
                "username": "HTTPx Scanner",
                "avatar_url": "https://example.com/httpx-logo.png"  # TODO: Add actual logo
            }
            
            response = await self.http_client.post(config.discord_webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Discord notification sent")
            
        except Exception as e:
            logger.error("Failed to send Discord notification", error=str(e))
    
    async def _send_discord_finding(self, finding: Finding, config: NotificationConfig):
        """Send Discord finding with rich embed"""
        try:
            color = {
                "critical": 0xFF0000,
                "high": 0xFF6600,
                "medium": 0xFFAA00,
                "low": 0x00AA00
            }.get(finding.severity, 0x808080)
            
            works_text = "✅ VERIFIED" if finding.works else "❓ Unverified"
            
            fields = [
                {"name": "Service", "value": finding.service.upper(), "inline": True},
                {"name": "Status", "value": works_text, "inline": True},
                {"name": "Confidence", "value": f"{finding.confidence:.1%}", "inline": True},
                {"name": "Evidence", "value": f"`{finding.evidence_masked}`", "inline": False}
            ]
            
            if finding.regions:
                fields.append({"name": "Regions", "value": ", ".join(finding.regions), "inline": False})
            
            if finding.capabilities:
                capabilities = ", ".join(finding.capabilities[:5])
                if len(finding.capabilities) > 5:
                    capabilities += f" (+{len(finding.capabilities) - 5} more)"
                fields.append({"name": "Capabilities", "value": capabilities, "inline": False})
            
            embed = {
                "title": f"🎯 New {finding.service.upper()} Hit",
                "url": finding.source_url,
                "color": color,
                "fields": fields,
                "footer": {"text": f"Crack ID: #{finding.crack_id} • Severity: {finding.severity.upper()}"},
                "timestamp": finding.created_at.isoformat()
            }
            
            payload = {
                "embeds": [embed],
                "username": "HTTPx Scanner",
                "avatar_url": "https://example.com/httpx-logo.png"  # TODO: Add actual logo
            }
            
            response = await self.http_client.post(config.discord_webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Discord finding notification sent")
            
        except Exception as e:
            logger.error("Failed to send Discord finding notification", error=str(e))
    
    async def _send_webhook(self, webhook_url: str, data: Dict[str, Any], config: NotificationConfig):
        """Send generic webhook with HMAC signature"""
        try:
            payload = json.dumps(data, sort_keys=True)
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "HTTPx-Scanner/1.0",
                "X-HTTPx-Event": data.get("event", "unknown"),
                "X-HTTPx-Timestamp": str(int(time.time()))
            }
            
            # Add HMAC signature if secret is configured
            if config.webhook_secret:
                signature = hmac.new(
                    config.webhook_secret.encode(),
                    payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-HTTPx-Signature"] = f"sha256={signature}"
            
            response = await self.http_client.post(
                webhook_url,
                content=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            logger.info("Webhook notification sent", url=webhook_url)
            
        except Exception as e:
            logger.error("Failed to send webhook notification", url=webhook_url, error=str(e))
    
    async def test_telegram(self, bot_token: str, chat_id: str) -> bool:
        """Test Telegram configuration"""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": "🧪 HTTPx Scanner test notification\n\nTelegram integration is working correctly!",
                "parse_mode": "Markdown"
            }
            
            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            
            logger.info("Telegram test notification sent successfully")
            return True
            
        except Exception as e:
            logger.error("Telegram test failed", error=str(e))
            return False
    
    async def test_slack(self, webhook_url: str) -> bool:
        """Test Slack configuration"""
        try:
            payload = {
                "text": "🧪 HTTPx Scanner test notification\n\nSlack integration is working correctly!",
                "username": "HTTPx Scanner",
                "icon_emoji": ":mag:"
            }
            
            response = await self.http_client.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Slack test notification sent successfully")
            return True
            
        except Exception as e:
            logger.error("Slack test failed", error=str(e))
            return False
    
    async def test_discord(self, webhook_url: str) -> bool:
        """Test Discord configuration"""
        try:
            embed = {
                "title": "🧪 HTTPx Scanner Test",
                "description": "Discord integration is working correctly!",
                "color": 0x7C3AED,
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {
                "embeds": [embed],
                "username": "HTTPx Scanner"
            }
            
            response = await self.http_client.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Discord test notification sent successfully")
            return True
            
        except Exception as e:
            logger.error("Discord test failed", error=str(e))
            return False
    
    async def test_webhook(self, webhook_url: str, secret: Optional[str] = None) -> bool:
        """Test generic webhook configuration"""
        try:
            data = {
                "event": "test",
                "message": "HTTPx Scanner webhook test",
                "timestamp": datetime.now().isoformat()
            }
            
            payload = json.dumps(data, sort_keys=True)
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "HTTPx-Scanner/1.0",
                "X-HTTPx-Event": "test",
                "X-HTTPx-Timestamp": str(int(time.time()))
            }
            
            if secret:
                signature = hmac.new(
                    secret.encode(),
                    payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-HTTPx-Signature"] = f"sha256={signature}"
            
            response = await self.http_client.post(
                webhook_url,
                content=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            logger.info("Webhook test notification sent successfully")
            return True
            
        except Exception as e:
            logger.error("Webhook test failed", error=str(e))
            return False


# Global notification manager instance
notification_manager = NotificationManager()