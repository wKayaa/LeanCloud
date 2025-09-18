"""
Modules Loader for optional wKayaa/modules_LeanCloud integration
"""

import sys
import importlib
from typing import Optional, Dict, Any, List
import structlog

logger = structlog.get_logger()


class ModulesLoader:
    """Loader for optional modules_LeanCloud package"""
    
    def __init__(self):
        self.modules_available = False
        self.modules_package = None
        self.registered_modules = {}
        
    def initialize(self):
        """Initialize and check for modules_LeanCloud availability"""
        try:
            # Try to import modules_LeanCloud
            import modules_LeanCloud
            self.modules_package = modules_LeanCloud
            self.modules_available = True
            
            logger.info("modules_LeanCloud found and loaded", 
                       version=getattr(modules_LeanCloud, '__version__', 'unknown'))
            
            # Call register function if available
            if hasattr(modules_LeanCloud, 'register'):
                try:
                    self.registered_modules = modules_LeanCloud.register(self)
                    logger.info("Modules registered successfully", 
                               count=len(self.registered_modules))
                except Exception as e:
                    logger.error("Failed to register modules", error=str(e))
            else:
                logger.warning("modules_LeanCloud found but no register() function")
                
        except ImportError:
            logger.info("modules_LeanCloud not found - continuing without optional modules")
            self.modules_available = False
        except Exception as e:
            logger.error("Error loading modules_LeanCloud", error=str(e))
            self.modules_available = False
    
    def is_available(self) -> bool:
        """Check if modules are available"""
        return self.modules_available
    
    def get_available_modules(self) -> Dict[str, Any]:
        """Get list of available modules"""
        return self.registered_modules
    
    def get_enrichers(self) -> List[Any]:
        """Get available enrichers"""
        enrichers = []
        for module_name, module_data in self.registered_modules.items():
            if 'enrichers' in module_data:
                enrichers.extend(module_data['enrichers'])
        return enrichers
    
    def get_validators(self) -> List[Any]:
        """Get available validators"""
        validators = []
        for module_name, module_data in self.registered_modules.items():
            if 'validators' in module_data:
                validators.extend(module_data['validators'])
        return validators
    
    def get_patterns(self) -> List[Dict[str, str]]:
        """Get additional secret patterns"""
        patterns = []
        for module_name, module_data in self.registered_modules.items():
            if 'patterns' in module_data:
                patterns.extend(module_data['patterns'])
        return patterns
    
    async def enrich_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a finding using available enrichers"""
        if not self.modules_available:
            return finding
        
        enriched_finding = finding.copy()
        
        for enricher in self.get_enrichers():
            try:
                if hasattr(enricher, 'enrich_async'):
                    enriched_finding = await enricher.enrich_async(enriched_finding)
                elif hasattr(enricher, 'enrich'):
                    enriched_finding = enricher.enrich(enriched_finding)
            except Exception as e:
                logger.error("Enricher failed", enricher=enricher.__class__.__name__, error=str(e))
        
        return enriched_finding
    
    async def validate_finding(self, finding: Dict[str, Any]) -> bool:
        """Validate a finding using available validators"""
        if not self.modules_available:
            return True
        
        for validator in self.get_validators():
            try:
                if hasattr(validator, 'validate_async'):
                    if not await validator.validate_async(finding):
                        return False
                elif hasattr(validator, 'validate'):
                    if not validator.validate(finding):
                        return False
            except Exception as e:
                logger.error("Validator failed", validator=validator.__class__.__name__, error=str(e))
        
        return True
    
    def get_installation_instructions(self) -> str:
        """Get installation instructions for modules_LeanCloud"""
        return """
To install modules_LeanCloud for enhanced functionality:

Option 1: Install from GitHub
pip install -e git+https://github.com/wKayaa/modules_LeanCloud.git

Option 2: Clone as submodule
git submodule add https://github.com/wKayaa/modules_LeanCloud.git modules_LeanCloud
export PYTHONPATH=$PYTHONPATH:$(pwd)

Option 3: Manual installation
git clone https://github.com/wKayaa/modules_LeanCloud.git
cd modules_LeanCloud
pip install -e .

After installation, restart the application to load the modules.
"""


# Global modules loader instance
modules_loader = ModulesLoader()


def get_modules_loader() -> ModulesLoader:
    """Get the global modules loader instance"""
    return modules_loader