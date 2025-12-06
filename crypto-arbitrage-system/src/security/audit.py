"""
Audit Logging System

Comprehensive audit trail for:
- Authentication events (login, logout, failures)
- Trading actions (orders, executions, cancellations)
- Configuration changes
- Security events (permission changes, key rotations)
- System events (startup, shutdown, errors)

Tamper-evident with hash chaining
"""

import os
import json
import hashlib
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from queue import Queue
import gzip

logger = logging.getLogger(__name__)


class AuditCategory(Enum):
    """Audit event categories"""
    AUTH = "authentication"
    TRADE = "trading"
    CONFIG = "configuration"
    SECURITY = "security"
    SYSTEM = "system"
    ACCESS = "access"


class AuditSeverity(Enum):
    """Event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """
    Immutable audit event record

    Contains all context needed for incident investigation
    """
    event_id: str
    timestamp: datetime
    category: AuditCategory
    severity: AuditSeverity
    action: str
    actor: str  # Username or 'system'
    actor_ip: str
    resource: str  # What was acted upon
    details: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None
    previous_hash: Optional[str] = None
    hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of event for tamper detection"""
        data = {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'severity': self.severity.value,
            'action': self.action,
            'actor': self.actor,
            'actor_ip': self.actor_ip,
            'resource': self.resource,
            'details': self.details,
            'success': self.success,
            'error_message': self.error_message,
            'previous_hash': self.previous_hash
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'severity': self.severity.value,
            'action': self.action,
            'actor': self.actor,
            'actor_ip': self.actor_ip,
            'resource': self.resource,
            'details': self.details,
            'success': self.success,
            'error_message': self.error_message,
            'previous_hash': self.previous_hash,
            'hash': self.hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AuditEvent':
        """Create from dictionary"""
        return cls(
            event_id=data['event_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            category=AuditCategory(data['category']),
            severity=AuditSeverity(data['severity']),
            action=data['action'],
            actor=data['actor'],
            actor_ip=data['actor_ip'],
            resource=data['resource'],
            details=data['details'],
            success=data['success'],
            error_message=data.get('error_message'),
            previous_hash=data.get('previous_hash'),
            hash=data.get('hash')
        )


class AuditLogger:
    """
    Centralized audit logging with tamper-evident storage

    Features:
    - Hash-chained events for integrity verification
    - Async event processing
    - Automatic log rotation
    - Compressed archival
    - Query interface for investigations
    """

    def __init__(
        self,
        log_dir: str = 'data/audit',
        max_file_size_mb: int = 100,
        retention_days: int = 90
    ):
        """
        Initialize audit logger

        Args:
            log_dir: Directory for audit logs
            max_file_size_mb: Max size before rotation
            retention_days: Days to keep audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.retention_days = retention_days

        self._current_file = self.log_dir / 'audit.log'
        self._lock = threading.Lock()
        self._last_hash: Optional[str] = None
        self._event_counter = 0

        # Load last hash for chain continuity
        self._load_last_hash()

        # Start background writer
        self._queue: Queue = Queue()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

        logger.info(f"Audit logger initialized: {self.log_dir}")

    def _load_last_hash(self):
        """Load the last hash from existing log for chain continuity"""
        if not self._current_file.exists():
            return

        try:
            with open(self._current_file, 'r') as f:
                # Read last line
                lines = f.readlines()
                if lines:
                    last_event = json.loads(lines[-1])
                    self._last_hash = last_event.get('hash')
                    self._event_counter = int(last_event.get('event_id', '0').split('-')[-1])
        except Exception as e:
            logger.warning(f"Could not load last audit hash: {e}")

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        self._event_counter += 1
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        return f"AUD-{date_str}-{self._event_counter:08d}"

    def _writer_loop(self):
        """Background thread for writing events"""
        while True:
            try:
                event = self._queue.get()
                if event is None:
                    break
                self._write_event(event)
            except Exception as e:
                logger.error(f"Audit write error: {e}")

    def _write_event(self, event: AuditEvent):
        """Write event to log file"""
        with self._lock:
            # Check rotation
            if self._current_file.exists():
                if self._current_file.stat().st_size >= self.max_file_size:
                    self._rotate_log()

            # Write event
            with open(self._current_file, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')

    def _rotate_log(self):
        """Rotate and compress old log"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        archive_name = self.log_dir / f'audit_{timestamp}.log.gz'

        # Compress current log
        with open(self._current_file, 'rb') as f_in:
            with gzip.open(archive_name, 'wb') as f_out:
                f_out.write(f_in.read())

        # Clear current log
        self._current_file.unlink()

        logger.info(f"Audit log rotated to {archive_name}")

        # Cleanup old archives
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff = datetime.now(timezone.utc).timestamp() - (self.retention_days * 86400)

        for archive in self.log_dir.glob('audit_*.log.gz'):
            if archive.stat().st_mtime < cutoff:
                archive.unlink()
                logger.info(f"Deleted old audit log: {archive}")

    def log(
        self,
        category: AuditCategory,
        action: str,
        actor: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        actor_ip: str = 'system'
    ) -> AuditEvent:
        """
        Log an audit event

        Args:
            category: Event category
            action: Action performed
            actor: Who performed (username or 'system')
            resource: What was acted upon
            details: Additional context
            success: Whether action succeeded
            error_message: Error if failed
            severity: Event severity
            actor_ip: Actor's IP address

        Returns:
            The logged AuditEvent
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(timezone.utc),
            category=category,
            severity=severity,
            action=action,
            actor=actor,
            actor_ip=actor_ip,
            resource=resource,
            details=details or {},
            success=success,
            error_message=error_message,
            previous_hash=self._last_hash
        )

        # Compute hash for tamper detection
        event.hash = event.compute_hash()
        self._last_hash = event.hash

        # Queue for async write
        self._queue.put(event)

        # Also log to standard logger for real-time monitoring
        log_msg = f"[AUDIT] {event.category.value}:{event.action} by {event.actor} on {event.resource}"
        if not success:
            log_msg += f" - FAILED: {error_message}"

        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AuditSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return event

    # Convenience methods for common events

    def log_login(
        self,
        username: str,
        ip_address: str,
        success: bool,
        error: Optional[str] = None,
        mfa_used: bool = False
    ):
        """Log authentication attempt"""
        self.log(
            category=AuditCategory.AUTH,
            action='login',
            actor=username,
            resource='auth_system',
            actor_ip=ip_address,
            details={'mfa_used': mfa_used},
            success=success,
            error_message=error,
            severity=AuditSeverity.WARNING if not success else AuditSeverity.INFO
        )

    def log_logout(self, username: str, ip_address: str):
        """Log logout"""
        self.log(
            category=AuditCategory.AUTH,
            action='logout',
            actor=username,
            resource='auth_system',
            actor_ip=ip_address
        )

    def log_trade(
        self,
        username: str,
        action: str,
        symbol: str,
        exchange: str,
        amount: float,
        price: float,
        success: bool,
        order_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log trading action"""
        self.log(
            category=AuditCategory.TRADE,
            action=action,
            actor=username,
            resource=f"{symbol}@{exchange}",
            details={
                'amount': amount,
                'price': price,
                'order_id': order_id
            },
            success=success,
            error_message=error,
            severity=AuditSeverity.ERROR if not success else AuditSeverity.INFO
        )

    def log_config_change(
        self,
        username: str,
        setting: str,
        old_value: Any,
        new_value: Any,
        ip_address: str = 'system'
    ):
        """Log configuration change"""
        self.log(
            category=AuditCategory.CONFIG,
            action='modify',
            actor=username,
            resource=setting,
            actor_ip=ip_address,
            details={
                'old_value': str(old_value),
                'new_value': str(new_value)
            },
            severity=AuditSeverity.WARNING
        )

    def log_security_event(
        self,
        action: str,
        actor: str,
        resource: str,
        details: Dict[str, Any],
        severity: AuditSeverity = AuditSeverity.WARNING,
        ip_address: str = 'system'
    ):
        """Log security-related event"""
        self.log(
            category=AuditCategory.SECURITY,
            action=action,
            actor=actor,
            resource=resource,
            actor_ip=ip_address,
            details=details,
            severity=severity
        )

    def log_system_event(
        self,
        action: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log system event"""
        self.log(
            category=AuditCategory.SYSTEM,
            action=action,
            actor='system',
            resource=resource,
            details=details or {},
            success=success,
            error_message=error,
            severity=AuditSeverity.ERROR if not success else AuditSeverity.INFO
        )

    def query(
        self,
        category: Optional[AuditCategory] = None,
        actor: Optional[str] = None,
        resource: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Query audit events

        Args:
            category: Filter by category
            actor: Filter by actor
            resource: Filter by resource
            start_time: Events after this time
            end_time: Events before this time
            success_only: Filter by success status
            limit: Maximum results

        Returns:
            List of matching AuditEvents
        """
        results = []

        if not self._current_file.exists():
            return results

        with open(self._current_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    event = AuditEvent.from_dict(data)

                    # Apply filters
                    if category and event.category != category:
                        continue
                    if actor and event.actor != actor:
                        continue
                    if resource and resource not in event.resource:
                        continue
                    if start_time and event.timestamp < start_time:
                        continue
                    if end_time and event.timestamp > end_time:
                        continue
                    if success_only is not None and event.success != success_only:
                        continue

                    results.append(event)

                    if len(results) >= limit:
                        break

                except Exception:
                    continue

        return results

    def verify_integrity(self) -> tuple:
        """
        Verify audit log integrity

        Returns:
            Tuple of (is_valid, broken_events)
        """
        if not self._current_file.exists():
            return True, []

        broken = []
        previous_hash = None

        with open(self._current_file, 'r') as f:
            for i, line in enumerate(f):
                try:
                    data = json.loads(line)
                    event = AuditEvent.from_dict(data)

                    # Verify chain
                    if event.previous_hash != previous_hash:
                        broken.append((i, event.event_id, 'broken_chain'))

                    # Verify hash
                    event_without_hash = AuditEvent(
                        event_id=event.event_id,
                        timestamp=event.timestamp,
                        category=event.category,
                        severity=event.severity,
                        action=event.action,
                        actor=event.actor,
                        actor_ip=event.actor_ip,
                        resource=event.resource,
                        details=event.details,
                        success=event.success,
                        error_message=event.error_message,
                        previous_hash=event.previous_hash
                    )

                    computed_hash = event_without_hash.compute_hash()
                    if computed_hash != event.hash:
                        broken.append((i, event.event_id, 'invalid_hash'))

                    previous_hash = event.hash

                except Exception as e:
                    broken.append((i, 'unknown', f'parse_error: {e}'))

        return len(broken) == 0, broken

    def shutdown(self):
        """Graceful shutdown"""
        self._queue.put(None)  # Signal writer to stop
        self._writer_thread.join(timeout=5)


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
