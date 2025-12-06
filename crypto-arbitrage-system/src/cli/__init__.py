"""
CLI Interface Module

Provides:
- Secure command-line dashboard
- Interactive configuration
- Real-time monitoring
- Credential management
"""

from .dashboard import Dashboard, run_dashboard
from .commands import CommandHandler

__all__ = ['Dashboard', 'run_dashboard', 'CommandHandler']
