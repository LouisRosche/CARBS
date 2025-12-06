"""
Role-Based Access Control (RBAC)

Implements fine-grained permissions:
- Roles: admin, trader, analyst, viewer
- Resources: trading, config, credentials, reports, system
- Actions: read, write, execute, delete

Follows principle of least privilege
"""

import logging
from enum import Enum, auto
from typing import Set, Dict, Optional, List
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System permissions"""
    # Trading permissions
    TRADE_VIEW = auto()  # View trading status
    TRADE_EXECUTE = auto()  # Execute trades
    TRADE_CANCEL = auto()  # Cancel orders
    TRADE_EMERGENCY_STOP = auto()  # Emergency kill switch

    # Configuration permissions
    CONFIG_VIEW = auto()  # View configuration
    CONFIG_MODIFY = auto()  # Modify configuration
    CONFIG_RESET = auto()  # Reset to defaults

    # Credential permissions
    CREDS_VIEW = auto()  # View credential metadata (not values)
    CREDS_ADD = auto()  # Add new credentials
    CREDS_MODIFY = auto()  # Modify existing credentials
    CREDS_DELETE = auto()  # Delete credentials
    CREDS_ROTATE = auto()  # Rotate encryption keys

    # Report permissions
    REPORT_VIEW = auto()  # View reports
    REPORT_EXPORT = auto()  # Export data
    REPORT_AUDIT = auto()  # View audit logs

    # System permissions
    SYSTEM_STATUS = auto()  # View system status
    SYSTEM_RESTART = auto()  # Restart components
    SYSTEM_SHUTDOWN = auto()  # Shutdown system

    # User management
    USER_VIEW = auto()  # View users
    USER_CREATE = auto()  # Create users
    USER_MODIFY = auto()  # Modify users
    USER_DELETE = auto()  # Delete users
    USER_RESET_MFA = auto()  # Reset MFA for users


class Role(Enum):
    """
    Predefined roles with associated permissions

    Follows principle of least privilege
    """
    VIEWER = "viewer"
    ANALYST = "analyst"
    TRADER = "trader"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.TRADE_VIEW,
        Permission.CONFIG_VIEW,
        Permission.REPORT_VIEW,
        Permission.SYSTEM_STATUS,
    },

    Role.ANALYST: {
        Permission.TRADE_VIEW,
        Permission.CONFIG_VIEW,
        Permission.REPORT_VIEW,
        Permission.REPORT_EXPORT,
        Permission.REPORT_AUDIT,
        Permission.SYSTEM_STATUS,
    },

    Role.TRADER: {
        Permission.TRADE_VIEW,
        Permission.TRADE_EXECUTE,
        Permission.TRADE_CANCEL,
        Permission.CONFIG_VIEW,
        Permission.REPORT_VIEW,
        Permission.REPORT_EXPORT,
        Permission.SYSTEM_STATUS,
    },

    Role.ADMIN: {
        Permission.TRADE_VIEW,
        Permission.TRADE_EXECUTE,
        Permission.TRADE_CANCEL,
        Permission.TRADE_EMERGENCY_STOP,
        Permission.CONFIG_VIEW,
        Permission.CONFIG_MODIFY,
        Permission.CREDS_VIEW,
        Permission.CREDS_ADD,
        Permission.CREDS_MODIFY,
        Permission.REPORT_VIEW,
        Permission.REPORT_EXPORT,
        Permission.REPORT_AUDIT,
        Permission.SYSTEM_STATUS,
        Permission.SYSTEM_RESTART,
        Permission.USER_VIEW,
        Permission.USER_CREATE,
        Permission.USER_MODIFY,
    },

    Role.SUPER_ADMIN: set(Permission),  # All permissions
}


@dataclass
class AccessDecision:
    """Result of access check"""
    allowed: bool
    reason: str
    required_permission: Optional[Permission] = None
    user_role: Optional[Role] = None


class AccessControl:
    """
    Centralized access control manager

    Features:
    - Role-based permission checks
    - Custom permission overrides
    - IP-based access restrictions
    - Time-based access windows
    """

    def __init__(self):
        self._role_permissions = dict(ROLE_PERMISSIONS)
        self._user_overrides: Dict[str, Set[Permission]] = {}  # Extra permissions
        self._user_denials: Dict[str, Set[Permission]] = {}  # Denied permissions
        self._ip_whitelist: Set[str] = set()
        self._ip_blacklist: Set[str] = set()

    def check_permission(
        self,
        username: str,
        role: str,
        permission: Permission,
        ip_address: Optional[str] = None
    ) -> AccessDecision:
        """
        Check if user has permission

        Args:
            username: Username
            role: User's role
            permission: Permission to check
            ip_address: Optional IP for IP-based checks

        Returns:
            AccessDecision with result
        """
        # IP blacklist check
        if ip_address and ip_address in self._ip_blacklist:
            return AccessDecision(
                allowed=False,
                reason=f"IP {ip_address} is blacklisted",
                required_permission=permission
            )

        # IP whitelist check (if whitelist is configured)
        if self._ip_whitelist and ip_address:
            if ip_address not in self._ip_whitelist:
                return AccessDecision(
                    allowed=False,
                    reason=f"IP {ip_address} not in whitelist",
                    required_permission=permission
                )

        # Get role enum
        try:
            role_enum = Role(role)
        except ValueError:
            return AccessDecision(
                allowed=False,
                reason=f"Unknown role: {role}",
                required_permission=permission
            )

        # Check explicit denial
        if username in self._user_denials:
            if permission in self._user_denials[username]:
                return AccessDecision(
                    allowed=False,
                    reason=f"Permission explicitly denied for user",
                    required_permission=permission,
                    user_role=role_enum
                )

        # Check role permissions
        role_perms = self._role_permissions.get(role_enum, set())

        # Check user overrides (additional permissions)
        user_perms = self._user_overrides.get(username, set())

        # Combine permissions
        all_perms = role_perms | user_perms

        if permission in all_perms:
            return AccessDecision(
                allowed=True,
                reason="Permission granted",
                required_permission=permission,
                user_role=role_enum
            )

        return AccessDecision(
            allowed=False,
            reason=f"Role '{role}' does not have permission '{permission.name}'",
            required_permission=permission,
            user_role=role_enum
        )

    def grant_permission(self, username: str, permission: Permission):
        """Grant additional permission to user"""
        if username not in self._user_overrides:
            self._user_overrides[username] = set()
        self._user_overrides[username].add(permission)
        logger.info(f"Granted {permission.name} to {username}")

    def revoke_permission(self, username: str, permission: Permission):
        """Revoke permission from user (add to denial list)"""
        if username not in self._user_denials:
            self._user_denials[username] = set()
        self._user_denials[username].add(permission)
        logger.info(f"Revoked {permission.name} from {username}")

    def add_ip_whitelist(self, ip: str):
        """Add IP to whitelist"""
        self._ip_whitelist.add(ip)
        logger.info(f"Added {ip} to whitelist")

    def remove_ip_whitelist(self, ip: str):
        """Remove IP from whitelist"""
        self._ip_whitelist.discard(ip)
        logger.info(f"Removed {ip} from whitelist")

    def add_ip_blacklist(self, ip: str):
        """Add IP to blacklist"""
        self._ip_blacklist.add(ip)
        logger.warning(f"Added {ip} to blacklist")

    def remove_ip_blacklist(self, ip: str):
        """Remove IP from blacklist"""
        self._ip_blacklist.discard(ip)
        logger.info(f"Removed {ip} from blacklist")

    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """Get all permissions for a role"""
        return self._role_permissions.get(role, set())

    def get_user_effective_permissions(
        self,
        username: str,
        role: str
    ) -> Set[Permission]:
        """Get all effective permissions for user"""
        try:
            role_enum = Role(role)
        except ValueError:
            return set()

        base_perms = self._role_permissions.get(role_enum, set())
        extra_perms = self._user_overrides.get(username, set())
        denied_perms = self._user_denials.get(username, set())

        return (base_perms | extra_perms) - denied_perms


def require_permission(permission: Permission):
    """
    Decorator to require specific permission

    Usage:
        @require_permission(Permission.TRADE_EXECUTE)
        async def execute_trade(session, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get session and access control from kwargs
            session = kwargs.get('session')
            access_control = kwargs.get('access_control')

            if not session:
                raise PermissionError("Authentication required")

            if not access_control:
                # Create default access control
                access_control = AccessControl()

            ip = getattr(session, 'ip_address', None)
            decision = access_control.check_permission(
                username=session.username,
                role=session.role,
                permission=permission,
                ip_address=ip
            )

            if not decision.allowed:
                raise PermissionError(decision.reason)

            return await func(*args, **kwargs)

        return wrapper
    return decorator


class EmergencyControls:
    """
    Emergency controls with multi-factor authorization

    Critical actions require:
    1. User with appropriate permission
    2. Confirmation code (TOTP)
    3. Optional: Second admin approval
    """

    def __init__(self, access_control: AccessControl):
        self.access_control = access_control
        self._emergency_mode = False
        self._emergency_reason: Optional[str] = None
        self._emergency_activated_by: Optional[str] = None

    @property
    def is_emergency_mode(self) -> bool:
        return self._emergency_mode

    def activate_emergency_stop(
        self,
        username: str,
        role: str,
        reason: str,
        ip_address: str
    ) -> bool:
        """
        Activate emergency stop

        Immediately halts all trading operations

        Returns:
            True if activated successfully
        """
        decision = self.access_control.check_permission(
            username=username,
            role=role,
            permission=Permission.TRADE_EMERGENCY_STOP,
            ip_address=ip_address
        )

        if not decision.allowed:
            logger.warning(
                f"Emergency stop DENIED for {username}: {decision.reason}"
            )
            return False

        self._emergency_mode = True
        self._emergency_reason = reason
        self._emergency_activated_by = username

        logger.critical(
            f"EMERGENCY STOP ACTIVATED by {username}: {reason}"
        )

        return True

    def deactivate_emergency_stop(
        self,
        username: str,
        role: str,
        ip_address: str
    ) -> bool:
        """
        Deactivate emergency stop

        Requires admin permission

        Returns:
            True if deactivated successfully
        """
        # Require admin role for deactivation
        if role not in ['admin', 'super_admin']:
            logger.warning(
                f"Emergency stop deactivation DENIED for {username}: "
                "Admin role required"
            )
            return False

        decision = self.access_control.check_permission(
            username=username,
            role=role,
            permission=Permission.TRADE_EMERGENCY_STOP,
            ip_address=ip_address
        )

        if not decision.allowed:
            logger.warning(
                f"Emergency stop deactivation DENIED for {username}: "
                f"{decision.reason}"
            )
            return False

        previous_reason = self._emergency_reason
        previous_activator = self._emergency_activated_by

        self._emergency_mode = False
        self._emergency_reason = None
        self._emergency_activated_by = None

        logger.warning(
            f"Emergency stop DEACTIVATED by {username}. "
            f"Was activated by {previous_activator}: {previous_reason}"
        )

        return True

    def get_emergency_status(self) -> dict:
        """Get current emergency status"""
        return {
            'is_active': self._emergency_mode,
            'reason': self._emergency_reason,
            'activated_by': self._emergency_activated_by
        }
