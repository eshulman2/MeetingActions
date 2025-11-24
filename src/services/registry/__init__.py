"""Registry service package.

This package contains the complete registry service implementation including:
- registry_service.py: Standalone registry server
- registry_client.py: Client for service discovery
- agent_registry.py: Registry data models
"""

from src.services.registry.agent_registry import AgentInfo
from src.services.registry.registry_client import RegistryClient, get_registry_client

__all__ = [
    "AgentInfo",
    "RegistryClient",
    "get_registry_client",
]
