import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from .models import ConfigModel, SecretPattern, ModuleType
import structlog

logger = structlog.get_logger()


class ConfigManager:
    """Configuration manager for httpxCloud v1"""
    
    def __init__(self, config_path: str = "data/config.yml"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config: Optional[ConfigModel] = None
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f)
                    
                    # Convert patterns to SecretPattern objects
                    if 'default_patterns' in data:
                        patterns = []
                        for pattern_data in data['default_patterns']:
                            if isinstance(pattern_data, dict):
                                patterns.append(SecretPattern(**pattern_data))
                            else:
                                patterns.append(pattern_data)
                        data['default_patterns'] = patterns
                    
                    self.config = ConfigModel(**data)
                    logger.info("Configuration loaded", path=str(self.config_path))
            else:
                self.config = self._create_default_config()
                self.save_config()
                logger.info("Default configuration created", path=str(self.config_path))
        except Exception as e:
            logger.error("Failed to load configuration", error=str(e))
            self.config = self._create_default_config()
    
    def _create_default_config(self) -> ConfigModel:
        """Create default configuration with enhanced patterns"""
        default_patterns = [
            # AWS patterns
            SecretPattern(
                name="AWS Access Key",
                pattern=r'AKIA[0-9A-Z]{16}',
                description="AWS Access Key ID",
                module_type=ModuleType.AWS
            ),
            SecretPattern(
                name="AWS Secret Key",
                pattern=r'[A-Za-z0-9/+=]{40}',
                description="AWS Secret Access Key",
                module_type=ModuleType.AWS
            ),
            
            # SendGrid patterns
            SecretPattern(
                name="SendGrid API Key",
                pattern=r'SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}',
                description="SendGrid API Key",
                module_type=ModuleType.SENDGRID
            ),
            
            # SMTP patterns
            SecretPattern(
                name="SMTP Credentials",
                pattern=r'smtp://[^:\s]+:[^@\s]+@[^:\s]+:\d+',
                description="SMTP Connection String",
                module_type=ModuleType.SMTP
            ),
            
            # Mailgun patterns
            SecretPattern(
                name="Mailgun API Key",
                pattern=r'key-[a-f0-9]{32}',
                description="Mailgun API Key",
                module_type=ModuleType.MAILGUN
            ),
            
            # Twilio patterns
            SecretPattern(
                name="Twilio Account SID",
                pattern=r'AC[a-f0-9]{32}',
                description="Twilio Account SID",
                module_type=ModuleType.TWILIO
            ),
            SecretPattern(
                name="Twilio Auth Token",
                pattern=r'[a-f0-9]{32}',
                description="Twilio Auth Token",
                module_type=ModuleType.TWILIO
            ),
            
            # Docker patterns
            SecretPattern(
                name="Docker API",
                pattern=r'tcp://[^/\s]+:2375',
                description="Docker API Endpoint (Insecure)",
                module_type=ModuleType.DOCKER
            ),
            SecretPattern(
                name="Docker API TLS",
                pattern=r'tcp://[^/\s]+:2376',
                description="Docker API Endpoint (TLS)",
                module_type=ModuleType.DOCKER
            ),
            
            # Kubernetes patterns
            SecretPattern(
                name="Kubernetes API",
                pattern=r'https?://[^/\s]+:6443',
                description="Kubernetes API Server",
                module_type=ModuleType.K8S
            ),
            SecretPattern(
                name="Kubernetes Token",
                pattern=r'eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]*',
                description="Kubernetes Service Account Token",
                module_type=ModuleType.K8S
            ),
            
            # Stripe patterns
            SecretPattern(
                name="Stripe Secret Key",
                pattern=r'sk_live_[A-Za-z0-9]{24}',
                description="Stripe Live Secret Key",
                module_type=ModuleType.STRIPE
            ),
            SecretPattern(
                name="Stripe Test Key",
                pattern=r'sk_test_[A-Za-z0-9]{24}',
                description="Stripe Test Secret Key",
                module_type=ModuleType.STRIPE
            ),
            
            # Generic patterns
            SecretPattern(
                name="Generic API Key",
                pattern=r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]+)["\']?',
                description="Generic API Key",
                module_type=ModuleType.GENERIC
            ),
            SecretPattern(
                name="Database Password",
                pattern=r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)["\']?',
                description="Database Password",
                module_type=ModuleType.GENERIC
            )
        ]
        
        return ConfigModel(
            auth_required=True,
            secret_key="httpx-scanner-change-me-in-production",
            first_run=True,
            rate_limit_per_minute=60,
            max_scan_retention_days=30,
            httpx_path="httpx",
            default_patterns=default_patterns,
            
            # v1 enhanced options
            max_concurrency=50000,
            adaptive_concurrency=True,
            enable_backpressure=True,
            queue_max_size=100000,
            batch_size=1000,
            
            # Database and Redis
            database_url="postgresql+asyncpg://httpx:httpx@localhost:5432/httpx_scanner",
            redis_url="redis://localhost:6379/0",
            
            # Notifications (disabled by default)
            telegram_bot_token=None,
            telegram_chat_id=None,
            slack_webhook_url=None,
            discord_webhook_url=None,
            webhook_secret=None
        )
    
    def save_config(self):
        """Save configuration to file"""
        try:
            data = self.config.model_dump()
            
            # Convert SecretPattern objects to dicts
            if 'default_patterns' in data:
                data['default_patterns'] = [
                    pattern.model_dump() if hasattr(pattern, 'model_dump') else pattern
                    for pattern in data['default_patterns']
                ]
            
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False)
            logger.info("Configuration saved", path=str(self.config_path))
        except Exception as e:
            logger.error("Failed to save configuration", error=str(e))
    
    def get_config(self) -> ConfigModel:
        """Get current configuration"""
        if not self.config:
            self.load_config()
        return self.config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration"""
        try:
            current_data = self.config.model_dump()
            current_data.update(updates)
            
            # Handle pattern updates
            if 'default_patterns' in updates:
                patterns = []
                for pattern_data in updates['default_patterns']:
                    if isinstance(pattern_data, dict):
                        patterns.append(SecretPattern(**pattern_data))
                    else:
                        patterns.append(pattern_data)
                current_data['default_patterns'] = patterns
            
            self.config = ConfigModel(**current_data)
            self.save_config()
            logger.info("Configuration updated")
            return True
        except Exception as e:
            logger.error("Failed to update configuration", error=str(e))
            return False
    
    def get_patterns_by_module(self, module_type: ModuleType) -> List[SecretPattern]:
        """Get patterns for specific module"""
        return [
            pattern for pattern in self.config.default_patterns
            if pattern.module_type == module_type
        ]
    
    def add_pattern(self, pattern: SecretPattern):
        """Add new pattern to configuration"""
        self.config.default_patterns.append(pattern)
        self.save_config()
        logger.info("Pattern added", name=pattern.name, module=pattern.module_type.value)
    
    def remove_pattern(self, pattern_name: str):
        """Remove pattern from configuration"""
        original_count = len(self.config.default_patterns)
        self.config.default_patterns = [
            p for p in self.config.default_patterns 
            if p.name != pattern_name
        ]
        
        if len(self.config.default_patterns) < original_count:
            self.save_config()
            logger.info("Pattern removed", name=pattern_name)
            return True
        
        logger.warning("Pattern not found", name=pattern_name)
        return False
    
    def get_database_url(self) -> str:
        """Get database URL"""
        return self.config.database_url or "sqlite+aiosqlite:///./httpx_scanner.db"
    
    def get_redis_url(self) -> str:
        """Get Redis URL"""
        return self.config.redis_url or "redis://localhost:6379/0"
    
    def is_notification_enabled(self, channel: str) -> bool:
        """Check if notification channel is enabled"""
        if channel == "telegram":
            return bool(self.config.telegram_bot_token and self.config.telegram_chat_id)
        elif channel == "slack":
            return bool(self.config.slack_webhook_url)
        elif channel == "discord":
            return bool(self.config.discord_webhook_url)
        elif channel == "webhook":
            return bool(self.config.webhook_secret)
        return False
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check required fields
        if not self.config.secret_key or self.config.secret_key == "change-me-in-production":
            issues.append("Secret key should be changed from default value")
        
        # Check concurrency limits
        if self.config.max_concurrency > 50000:
            issues.append("Max concurrency exceeds recommended limit of 50,000")
        
        # Check database URL
        if not self.config.database_url:
            issues.append("Database URL not configured")
        
        # Check Redis URL
        if not self.config.redis_url:
            issues.append("Redis URL not configured")
        
        # Check notification config
        if self.config.telegram_bot_token and not self.config.telegram_chat_id:
            issues.append("Telegram bot token provided but chat ID missing")
        
        if self.config.telegram_chat_id and not self.config.telegram_bot_token:
            issues.append("Telegram chat ID provided but bot token missing")
        
        # Check patterns
        if not self.config.default_patterns:
            issues.append("No default patterns configured")
        
        return issues


# Global configuration manager
config_manager = ConfigManager()