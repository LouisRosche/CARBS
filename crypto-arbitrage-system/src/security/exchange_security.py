"""
Exchange Security Module

Provides:
- API key validation and permission checking
- IP whitelist enforcement
- Trade-only vs withdrawal key separation
- Exchange-specific security configurations
- Connection monitoring and anomaly detection
- API key rotation reminders
"""

import os
import re
import socket
import hashlib
import logging
import ipaddress
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from pathlib import Path
import json
import aiohttp

logger = logging.getLogger(__name__)


class KeyPermission(Flag):
    """API key permission flags"""
    NONE = 0
    READ = auto()           # Read account info, balances
    SPOT_TRADE = auto()     # Spot trading
    MARGIN_TRADE = auto()   # Margin trading
    FUTURES_TRADE = auto()  # Futures trading
    WITHDRAW = auto()       # Withdrawal capability
    TRANSFER = auto()       # Internal transfers

    # Common combinations
    READ_ONLY = READ
    TRADE_ONLY = READ | SPOT_TRADE
    FULL_TRADE = READ | SPOT_TRADE | MARGIN_TRADE | FUTURES_TRADE
    DANGEROUS = WITHDRAW | TRANSFER


class ExchangeSecurityLevel(Enum):
    """Exchange security tier based on configuration"""
    CRITICAL = "critical"   # Withdrawal enabled - highest security
    HIGH = "high"           # Trading enabled
    MEDIUM = "medium"       # Read-only with transfers
    LOW = "low"             # Read-only
    UNKNOWN = "unknown"     # Permissions not verified


@dataclass
class ExchangeKeyConfig:
    """Configuration for an exchange API key"""
    exchange: str
    key_id: str  # First 8 chars of key (for identification)
    permissions: KeyPermission
    ip_whitelist: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = None
    last_verified: datetime = None
    rotation_reminder_days: int = 90
    is_active: bool = True

    # Security metadata
    security_level: ExchangeSecurityLevel = ExchangeSecurityLevel.UNKNOWN
    has_withdrawal: bool = False
    verified_permissions: bool = False


@dataclass
class SecurityIncident:
    """Record of security-related incident"""
    incident_id: str
    timestamp: datetime
    exchange: str
    incident_type: str  # "ip_mismatch", "permission_change", "suspicious_activity"
    severity: str  # "low", "medium", "high", "critical"
    details: Dict
    resolved: bool = False
    resolution_notes: str = ""


class IPWhitelistEnforcer:
    """
    Enforces IP whitelist for exchange connections

    Features:
    - Validates outgoing connection IP
    - Monitors for IP changes
    - Alerts on mismatches
    """

    def __init__(self, alert_callback=None):
        self.alert_callback = alert_callback
        self._exchange_ips: Dict[str, Set[str]] = {}
        self._our_ips: Set[str] = set()
        self._last_ip_check: datetime = None

    async def get_current_ip(self) -> str:
        """Get current outbound IP address"""
        try:
            async with aiohttp.ClientSession() as session:
                # Use multiple services for reliability
                services = [
                    'https://api.ipify.org',
                    'https://ifconfig.me/ip',
                    'https://icanhazip.com'
                ]

                for service in services:
                    try:
                        async with session.get(service, timeout=5) as resp:
                            if resp.status == 200:
                                ip = (await resp.text()).strip()
                                return ip
                    except Exception:
                        continue

            return None
        except Exception as e:
            logger.error(f"Failed to get current IP: {e}")
            return None

    async def verify_ip_whitelisted(
        self,
        exchange: str,
        whitelisted_ips: List[str]
    ) -> tuple:
        """
        Verify our IP is in exchange whitelist

        Returns:
            (is_whitelisted: bool, current_ip: str, message: str)
        """
        current_ip = await self.get_current_ip()

        if not current_ip:
            return False, None, "Could not determine current IP"

        self._our_ips.add(current_ip)
        self._last_ip_check = datetime.now(timezone.utc)

        # Check against whitelist
        for whitelisted in whitelisted_ips:
            try:
                # Handle CIDR notation
                if '/' in whitelisted:
                    network = ipaddress.ip_network(whitelisted, strict=False)
                    if ipaddress.ip_address(current_ip) in network:
                        return True, current_ip, f"IP {current_ip} in whitelisted network {whitelisted}"
                else:
                    if current_ip == whitelisted:
                        return True, current_ip, f"IP {current_ip} is whitelisted"
            except ValueError as e:
                logger.warning(f"Invalid whitelist entry {whitelisted}: {e}")

        return False, current_ip, f"IP {current_ip} not in whitelist for {exchange}"

    async def monitor_ip_changes(self, interval_seconds: int = 300):
        """Monitor for IP changes (e.g., VPN disconnect)"""
        last_ip = await self.get_current_ip()

        while True:
            await asyncio.sleep(interval_seconds)

            current_ip = await self.get_current_ip()

            if current_ip and current_ip != last_ip:
                logger.warning(f"IP changed from {last_ip} to {current_ip}")

                if self.alert_callback:
                    await self.alert_callback(
                        "IP Address Changed",
                        f"Your IP changed from {last_ip} to {current_ip}. "
                        "Verify exchange whitelists are updated."
                    )

                last_ip = current_ip


class ExchangeKeyValidator:
    """
    Validates API key permissions and security

    Features:
    - Permission verification per exchange
    - Withdrawal capability detection
    - Key rotation reminders
    - Security recommendations
    """

    # Exchange-specific API endpoints for permission checking
    EXCHANGE_ENDPOINTS = {
        'binance': {
            'account': '/api/v3/account',
            'api_restrictions': '/sapi/v1/account/apiRestrictions'
        },
        'coinbase': {
            'accounts': '/v2/accounts'
        },
        'kraken': {
            'balance': '/0/private/Balance'
        },
        'kucoin': {
            'accounts': '/api/v1/accounts'
        }
    }

    def __init__(self, secrets_manager=None, alert_callback=None):
        self.secrets_manager = secrets_manager
        self.alert_callback = alert_callback
        self._key_configs: Dict[str, ExchangeKeyConfig] = {}
        self._incidents: List[SecurityIncident] = []

    async def verify_binance_permissions(
        self,
        api_key: str,
        api_secret: str
    ) -> KeyPermission:
        """Verify Binance API key permissions"""
        import hmac
        import time

        permissions = KeyPermission.NONE

        try:
            timestamp = int(time.time() * 1000)

            async with aiohttp.ClientSession() as session:
                # Check API restrictions endpoint
                query = f"timestamp={timestamp}"
                signature = hmac.new(
                    api_secret.encode(),
                    query.encode(),
                    hashlib.sha256
                ).hexdigest()

                url = f"https://api.binance.com/sapi/v1/account/apiRestrictions?{query}&signature={signature}"
                headers = {'X-MBX-APIKEY': api_key}

                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Parse Binance permissions
                        if data.get('enableReading'):
                            permissions |= KeyPermission.READ
                        if data.get('enableSpotAndMarginTrading'):
                            permissions |= KeyPermission.SPOT_TRADE
                        if data.get('enableMargin'):
                            permissions |= KeyPermission.MARGIN_TRADE
                        if data.get('enableFutures'):
                            permissions |= KeyPermission.FUTURES_TRADE
                        if data.get('enableWithdrawals'):
                            permissions |= KeyPermission.WITHDRAW
                        if data.get('enableInternalTransfer'):
                            permissions |= KeyPermission.TRANSFER

                        logger.info(f"Binance permissions verified: {permissions}")
                    else:
                        logger.warning(f"Failed to verify Binance permissions: {resp.status}")

        except Exception as e:
            logger.error(f"Error verifying Binance permissions: {e}")

        return permissions

    async def verify_key_permissions(
        self,
        exchange: str,
        api_key: str,
        api_secret: str
    ) -> ExchangeKeyConfig:
        """
        Verify API key permissions for any supported exchange
        """
        key_id = api_key[:8] if len(api_key) >= 8 else api_key

        permissions = KeyPermission.NONE

        if exchange.lower() == 'binance':
            permissions = await self.verify_binance_permissions(api_key, api_secret)
        else:
            # For other exchanges, assume read + trade until verified
            logger.warning(f"Permission verification not implemented for {exchange}")
            permissions = KeyPermission.READ | KeyPermission.SPOT_TRADE

        # Determine security level
        has_withdrawal = bool(permissions & KeyPermission.WITHDRAW)

        if has_withdrawal:
            security_level = ExchangeSecurityLevel.CRITICAL
        elif permissions & (KeyPermission.SPOT_TRADE | KeyPermission.MARGIN_TRADE | KeyPermission.FUTURES_TRADE):
            security_level = ExchangeSecurityLevel.HIGH
        elif permissions & KeyPermission.TRANSFER:
            security_level = ExchangeSecurityLevel.MEDIUM
        elif permissions & KeyPermission.READ:
            security_level = ExchangeSecurityLevel.LOW
        else:
            security_level = ExchangeSecurityLevel.UNKNOWN

        config = ExchangeKeyConfig(
            exchange=exchange,
            key_id=key_id,
            permissions=permissions,
            security_level=security_level,
            has_withdrawal=has_withdrawal,
            verified_permissions=True,
            last_verified=datetime.now(timezone.utc)
        )

        self._key_configs[f"{exchange}:{key_id}"] = config

        # Alert if withdrawal enabled
        if has_withdrawal and self.alert_callback:
            await self.alert_callback(
                "Security Warning: Withdrawal Enabled",
                f"API key for {exchange} has withdrawal permissions. "
                "Consider using a trade-only key for arbitrage."
            )

        return config

    def get_security_recommendations(
        self,
        config: ExchangeKeyConfig
    ) -> List[Dict]:
        """
        Get security recommendations for an API key
        """
        recommendations = []

        # Withdrawal warning
        if config.has_withdrawal:
            recommendations.append({
                "severity": "critical",
                "title": "Disable Withdrawal Permissions",
                "description": (
                    f"Your {config.exchange} API key has withdrawal permissions. "
                    "For arbitrage trading, you only need trade permissions. "
                    "Create a new key with trade-only access and disable withdrawals."
                ),
                "action": f"Visit {config.exchange} API settings and create a trade-only key"
            })

        # IP whitelist
        if not config.ip_whitelist:
            recommendations.append({
                "severity": "high",
                "title": "Enable IP Whitelist",
                "description": (
                    f"No IP whitelist configured for {config.exchange}. "
                    "IP whitelisting prevents unauthorized use of your API key "
                    "even if it's compromised."
                ),
                "action": f"Add your server IP to {config.exchange} API whitelist"
            })

        # Key rotation
        if config.created_at:
            age_days = (datetime.now(timezone.utc) - config.created_at).days
            if age_days > config.rotation_reminder_days:
                recommendations.append({
                    "severity": "medium",
                    "title": "Rotate API Key",
                    "description": (
                        f"Your {config.exchange} API key is {age_days} days old. "
                        "Regular key rotation reduces risk from potential exposure."
                    ),
                    "action": f"Generate new API key on {config.exchange} and update credentials"
                })

        # 2FA on exchange
        recommendations.append({
            "severity": "high",
            "title": "Verify Exchange 2FA",
            "description": (
                f"Ensure 2FA (preferably hardware key or TOTP) is enabled on your "
                f"{config.exchange} account for account-level protection."
            ),
            "action": f"Check {config.exchange} security settings for 2FA status"
        })

        return recommendations


class ExchangeSecurityManager:
    """
    Central manager for exchange security

    Coordinates:
    - IP whitelist enforcement
    - Key validation
    - Security monitoring
    - Incident tracking
    """

    def __init__(
        self,
        secrets_manager=None,
        alert_callback=None,
        data_dir: Path = None
    ):
        self.secrets_manager = secrets_manager
        self.alert_callback = alert_callback
        self.data_dir = data_dir or Path("data/security")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.ip_enforcer = IPWhitelistEnforcer(alert_callback)
        self.key_validator = ExchangeKeyValidator(secrets_manager, alert_callback)

        self._exchange_configs: Dict[str, Dict] = {}
        self._incidents: List[SecurityIncident] = []

        self._load_configs()

    def _load_configs(self):
        """Load exchange security configurations"""
        config_file = self.data_dir / "exchange_security.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    self._exchange_configs = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load exchange configs: {e}")

    def _save_configs(self):
        """Save exchange security configurations"""
        config_file = self.data_dir / "exchange_security.json"
        with open(config_file, 'w') as f:
            json.dump(self._exchange_configs, f, indent=2, default=str)

    async def register_exchange(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        ip_whitelist: List[str] = None
    ) -> Dict:
        """
        Register and validate exchange API credentials

        Returns security status and recommendations.
        """
        logger.info(f"Registering exchange: {exchange}")

        # Verify permissions
        key_config = await self.key_validator.verify_key_permissions(
            exchange, api_key, api_secret
        )

        # Verify IP if whitelist provided
        ip_status = None
        if ip_whitelist:
            key_config.ip_whitelist = ip_whitelist
            is_whitelisted, current_ip, message = await self.ip_enforcer.verify_ip_whitelisted(
                exchange, ip_whitelist
            )
            ip_status = {
                "is_whitelisted": is_whitelisted,
                "current_ip": current_ip,
                "message": message
            }

            if not is_whitelisted:
                self._log_incident(
                    exchange=exchange,
                    incident_type="ip_mismatch",
                    severity="high",
                    details=ip_status
                )

        # Get recommendations
        recommendations = self.key_validator.get_security_recommendations(key_config)

        # Store config
        self._exchange_configs[exchange] = {
            "key_id": key_config.key_id,
            "permissions": key_config.permissions.value,
            "security_level": key_config.security_level.value,
            "has_withdrawal": key_config.has_withdrawal,
            "ip_whitelist": ip_whitelist or [],
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_verified": datetime.now(timezone.utc).isoformat()
        }
        self._save_configs()

        return {
            "exchange": exchange,
            "security_level": key_config.security_level.value,
            "permissions": str(key_config.permissions),
            "has_withdrawal": key_config.has_withdrawal,
            "ip_status": ip_status,
            "recommendations": recommendations,
            "is_secure": (
                not key_config.has_withdrawal
                and bool(ip_whitelist)
                and (ip_status is None or ip_status["is_whitelisted"])
            )
        }

    def _log_incident(
        self,
        exchange: str,
        incident_type: str,
        severity: str,
        details: Dict
    ):
        """Log a security incident"""
        incident = SecurityIncident(
            incident_id=hashlib.sha256(
                f"{exchange}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
            timestamp=datetime.now(timezone.utc),
            exchange=exchange,
            incident_type=incident_type,
            severity=severity,
            details=details
        )

        self._incidents.append(incident)
        logger.warning(f"Security incident: {incident_type} on {exchange} ({severity})")

        # Persist incidents
        incidents_file = self.data_dir / "incidents.json"
        with open(incidents_file, 'w') as f:
            json.dump([
                {
                    "incident_id": i.incident_id,
                    "timestamp": i.timestamp.isoformat(),
                    "exchange": i.exchange,
                    "incident_type": i.incident_type,
                    "severity": i.severity,
                    "details": i.details,
                    "resolved": i.resolved
                }
                for i in self._incidents
            ], f, indent=2)

    async def run_security_check(self) -> Dict:
        """
        Run comprehensive security check on all exchanges

        Returns summary of security status.
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchanges": {},
            "overall_status": "secure",
            "critical_issues": [],
            "warnings": []
        }

        for exchange, config in self._exchange_configs.items():
            exchange_result = {
                "security_level": config.get("security_level", "unknown"),
                "has_withdrawal": config.get("has_withdrawal", False),
                "ip_whitelisted": bool(config.get("ip_whitelist")),
                "issues": []
            }

            # Check withdrawal
            if config.get("has_withdrawal"):
                issue = f"{exchange}: Withdrawal permissions enabled"
                exchange_result["issues"].append(issue)
                results["critical_issues"].append(issue)
                results["overall_status"] = "critical"

            # Check IP whitelist
            if config.get("ip_whitelist"):
                is_ok, current_ip, msg = await self.ip_enforcer.verify_ip_whitelisted(
                    exchange, config["ip_whitelist"]
                )
                if not is_ok:
                    issue = f"{exchange}: {msg}"
                    exchange_result["issues"].append(issue)
                    results["critical_issues"].append(issue)
                    results["overall_status"] = "critical"
            else:
                issue = f"{exchange}: No IP whitelist configured"
                exchange_result["issues"].append(issue)
                results["warnings"].append(issue)
                if results["overall_status"] == "secure":
                    results["overall_status"] = "warning"

            results["exchanges"][exchange] = exchange_result

        return results

    def get_trade_readiness(self, exchange: str) -> tuple:
        """
        Check if exchange is ready for trading

        Returns:
            (is_ready: bool, reason: str)
        """
        if exchange not in self._exchange_configs:
            return False, f"Exchange {exchange} not registered"

        config = self._exchange_configs[exchange]

        # Check critical issues
        if config.get("security_level") == "critical":
            return False, "Withdrawal permissions enabled - use trade-only key"

        # Check permissions
        permissions = KeyPermission(config.get("permissions", 0))
        if not (permissions & KeyPermission.SPOT_TRADE):
            return False, "API key lacks trading permissions"

        return True, "Exchange ready for trading"


# Best practices documentation
EXCHANGE_SECURITY_BEST_PRACTICES = """
# Exchange API Security Best Practices

## 1. API Key Permissions

### Trade-Only Keys (Recommended for Arbitrage)
- Enable: Read, Spot Trading
- Disable: Withdrawals, Margin (unless needed), Internal Transfers
- Why: Limits damage if key is compromised

### Read-Only Keys (For Monitoring)
- Enable: Read only
- Use for: Price monitoring, balance checks, analytics

### NEVER use Full-Access Keys for Automated Trading
- Withdrawal permissions are unnecessary for arbitrage
- Create separate keys for manual withdrawals

## 2. IP Whitelisting

### Always Enable IP Restrictions
- Whitelist only IPs that need access
- For home use: Use your home IP
- For VPS: Use server's static IP
- For dynamic IP: Consider VPN with static IP

### Handling Dynamic IPs
- Use a VPN service with static IP
- Update whitelist when IP changes
- Monitor for IP change alerts

## 3. Key Rotation

### Rotate Keys Regularly
- Recommended: Every 90 days
- Required: After any security incident
- Process: Create new key, update CARBS, delete old key

### Rotation Checklist
1. Create new key on exchange
2. Test new key in paper mode
3. Update production credentials
4. Verify trading works
5. Delete old key on exchange

## 4. Exchange Account Security

### Enable All Available Security Features
- Hardware key (YubiKey) - Best
- TOTP app (Google Auth) - Good
- SMS 2FA - Better than nothing

### Address Whitelisting
- Enable on exchange if available
- Pre-approve withdrawal addresses
- Adds delay but prevents theft

### API Trading Settings
- Enable anti-phishing code
- Set up withdrawal address whitelist
- Enable login notifications

## 5. Monitoring

### Set Up Alerts For
- Failed login attempts
- New API key creation
- Withdrawal requests
- Large trades
- IP address changes

### Regular Audits
- Review API key list monthly
- Check for unused keys
- Verify permissions haven't changed
"""


__all__ = [
    "KeyPermission",
    "ExchangeSecurityLevel",
    "ExchangeKeyConfig",
    "IPWhitelistEnforcer",
    "ExchangeKeyValidator",
    "ExchangeSecurityManager",
    "SecurityIncident",
    "EXCHANGE_SECURITY_BEST_PRACTICES"
]
