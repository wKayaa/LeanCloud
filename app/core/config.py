import os
import yaml
from pathlib import Path
from typing import List, Dict, Any
from .models import ConfigModel, SecretPattern


class Config:
    def __init__(self, config_path: str = "data/config.yml"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_config()
    
    def _get_default_patterns(self) -> List[SecretPattern]:
        """Get default regex patterns for secret detection"""
        return [
            SecretPattern(
                name="AWS Access Key",
                pattern=r"AKIA[A-Z0-9]{16}",
                description="AWS Access Key ID"
            ),
            SecretPattern(
                name="SendGrid API Key",
                pattern=r"SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}",
                description="SendGrid API Key"
            ),
            SecretPattern(
                name="Mailgun API Key",
                pattern=r"key-[0-9a-zA-Z]{32}",
                description="Mailgun API Key"
            ),
            SecretPattern(
                name="Stripe Live Key",
                pattern=r"sk_live_[0-9A-Za-z]{24,99}",
                description="Stripe Live Secret Key"
            ),
            SecretPattern(
                name="Brevo API Key",
                pattern=r"xkeysib-[a-f0-9]{64}-[a-zA-Z0-9]{16}",
                description="Brevo (Sendinblue) API Key"
            ),
            SecretPattern(
                name="Twilio SID",
                pattern=r"AC[a-f0-9]{32}",
                description="Twilio Account SID"
            ),
            SecretPattern(
                name="Alibaba Access Key",
                pattern=r"(?i)\b((LTAI)(?i)[a-z0-9]{20})(?:['|\"|\\n|\\r|\\s|\\x60]|$)",
                description="Alibaba Cloud Access Key"
            ),
            SecretPattern(
                name="AWS SES SMTP",
                pattern=r"email-smtp\.(us|eu|ap|ca|cn|sa)-(central|(north|south)?(west|east)?)-[0-9]{1}\.amazonaws\.com",
                description="AWS SES SMTP Endpoint"
            )
        ]
    
    def _load_config(self) -> ConfigModel:
        """Load configuration from YAML file or create default"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                # Convert patterns to SecretPattern objects
                if 'default_patterns' in config_data:
                    patterns = []
                    for p in config_data['default_patterns']:
                        patterns.append(SecretPattern(**p))
                    config_data['default_patterns'] = patterns
                return ConfigModel(**config_data)
        else:
            # Create default config
            default_config = ConfigModel(default_patterns=self._get_default_patterns())
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: ConfigModel):
        """Save configuration to YAML file"""
        config_dict = config.model_dump()
        # Convert SecretPattern objects to dicts for YAML serialization
        if 'default_patterns' in config_dict:
            patterns = []
            for pattern in config_dict['default_patterns']:
                if isinstance(pattern, SecretPattern):
                    patterns.append(pattern.model_dump())
                else:
                    patterns.append(pattern)
            config_dict['default_patterns'] = patterns
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
        self._config = config
    
    def get_config(self) -> ConfigModel:
        """Get current configuration"""
        return self._config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with partial updates"""
        current_dict = self._config.model_dump()
        current_dict.update(updates)
        self._config = ConfigModel(**current_dict)
        self.save_config(self._config)


# Global config instance
config_manager = Config()