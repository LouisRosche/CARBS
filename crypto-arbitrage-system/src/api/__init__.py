"""
API Module

Secure REST API for:
- System monitoring
- Trading controls
- Configuration management
- Webhook integrations
"""

from .server import create_app, run_api_server
from .middleware import SecurityMiddleware

__all__ = ['create_app', 'run_api_server', 'SecurityMiddleware']
