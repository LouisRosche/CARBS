"""
Security Module - Zero-Trust Architecture

Provides:
- Fernet encryption for secrets at rest
- TOTP-based two-factor authentication
- Role-based access control (RBAC)
- Comprehensive audit logging
- Session management with JWT
- Rate limiting and IP controls
"""

from .encryption import SecretsManager, EncryptedConfig
from .auth import AuthenticationManager, Session, require_auth
from .audit import AuditLogger, AuditEvent
from .access_control import AccessControl, Permission, Role

__all__ = [
    'SecretsManager',
    'EncryptedConfig',
    'AuthenticationManager',
    'Session',
    'require_auth',
    'AuditLogger',
    'AuditEvent',
    'AccessControl',
    'Permission',
    'Role'
]
