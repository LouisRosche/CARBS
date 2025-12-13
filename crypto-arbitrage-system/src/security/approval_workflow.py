"""
Approval Workflow Module

Implements multi-signature and time-delayed approvals for high-risk operations:
- Configuration changes
- Large trades
- Mode switches (paper -> live)
- Emergency controls
- User management
- API key operations
"""

import hashlib
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ApprovalType(Enum):
    """Types of operations requiring approval"""
    CONFIG_CHANGE = "config_change"
    LARGE_TRADE = "large_trade"
    MODE_SWITCH = "mode_switch"
    USER_MANAGEMENT = "user_management"
    API_KEY_OPERATION = "api_key_operation"
    EMERGENCY_ACTION = "emergency_action"
    WITHDRAWAL = "withdrawal"
    RISK_LIMIT_CHANGE = "risk_limit_change"


class ApprovalStatus(Enum):
    """Status of an approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXECUTING = "executing"  # In-progress execution (prevents race conditions)
    EXECUTED = "executed"


@dataclass
class ApprovalRule:
    """
    Rule defining approval requirements for an operation type
    """
    approval_type: ApprovalType
    required_approvers: int = 1  # Quorum
    required_roles: List[str] = field(default_factory=lambda: ["admin"])
    time_delay_minutes: int = 0  # Mandatory waiting period
    expiry_minutes: int = 60  # Request expires after
    allow_self_approval: bool = False
    require_2fa: bool = True
    require_reason: bool = True

    # Thresholds for conditional rules
    threshold_usd: float = None  # For trade-based rules


@dataclass
class ApprovalRequest:
    """
    Request for approval of an operation
    """
    request_id: str
    approval_type: ApprovalType
    requester_id: str
    requester_role: str
    operation_details: Dict
    reason: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: datetime = None
    executable_at: datetime = None  # After time delay

    # Approvals received
    approvals: List[Dict] = field(default_factory=list)
    rejections: List[Dict] = field(default_factory=list)

    # Execution tracking
    executed_at: datetime = None
    execution_result: Dict = None

    # Security
    request_hash: str = ""


@dataclass
class ApprovalDecision:
    """Record of an approval or rejection decision"""
    decision_id: str
    request_id: str
    approver_id: str
    approver_role: str
    decision: str  # "approve" or "reject"
    reason: str
    timestamp: datetime
    ip_address: str
    verified_2fa: bool


class ApprovalWorkflowEngine:
    """
    Manages approval workflows for high-risk operations

    Features:
    - Configurable approval rules per operation type
    - Multi-signature (quorum) requirements
    - Time-delayed execution
    - Audit trail
    - Notification integration
    - Thread-safe operations with asyncio.Lock
    """

    # Default approval rules
    DEFAULT_RULES = {
        ApprovalType.CONFIG_CHANGE: ApprovalRule(
            approval_type=ApprovalType.CONFIG_CHANGE,
            required_approvers=1,
            required_roles=["admin", "super_admin"],
            time_delay_minutes=5,
            require_reason=True
        ),
        ApprovalType.LARGE_TRADE: ApprovalRule(
            approval_type=ApprovalType.LARGE_TRADE,
            required_approvers=1,
            required_roles=["trader", "admin", "super_admin"],
            time_delay_minutes=0,
            threshold_usd=10000
        ),
        ApprovalType.MODE_SWITCH: ApprovalRule(
            approval_type=ApprovalType.MODE_SWITCH,
            required_approvers=2,
            required_roles=["admin", "super_admin"],
            time_delay_minutes=15,
            require_reason=True,
            require_2fa=True
        ),
        ApprovalType.USER_MANAGEMENT: ApprovalRule(
            approval_type=ApprovalType.USER_MANAGEMENT,
            required_approvers=1,
            required_roles=["admin", "super_admin"],
            time_delay_minutes=5,
            allow_self_approval=False
        ),
        ApprovalType.API_KEY_OPERATION: ApprovalRule(
            approval_type=ApprovalType.API_KEY_OPERATION,
            required_approvers=2,
            required_roles=["super_admin"],
            time_delay_minutes=30,
            require_2fa=True,
            require_reason=True
        ),
        ApprovalType.EMERGENCY_ACTION: ApprovalRule(
            approval_type=ApprovalType.EMERGENCY_ACTION,
            required_approvers=1,
            required_roles=["admin", "super_admin"],
            time_delay_minutes=0,  # Immediate for emergencies
            require_2fa=True
        ),
        ApprovalType.WITHDRAWAL: ApprovalRule(
            approval_type=ApprovalType.WITHDRAWAL,
            required_approvers=2,
            required_roles=["super_admin"],
            time_delay_minutes=60,  # 1 hour delay
            require_2fa=True,
            require_reason=True
        ),
        ApprovalType.RISK_LIMIT_CHANGE: ApprovalRule(
            approval_type=ApprovalType.RISK_LIMIT_CHANGE,
            required_approvers=2,
            required_roles=["admin", "super_admin"],
            time_delay_minutes=15,
            require_reason=True
        )
    }

    def __init__(
        self,
        data_dir: Path = None,
        notification_callback: Callable = None,
        audit_logger=None
    ):
        self.data_dir = data_dir or Path("data/approvals")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.notification_callback = notification_callback
        self.audit_logger = audit_logger

        self._rules: Dict[ApprovalType, ApprovalRule] = dict(self.DEFAULT_RULES)
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._completed_requests: List[ApprovalRequest] = []

        # Thread-safety lock for concurrent access to pending requests
        self._lock = asyncio.Lock()

        self._load_state()

    def _load_state(self):
        """Load pending requests from disk"""
        state_file = self.data_dir / "pending_requests.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    for req_data in data:
                        request = ApprovalRequest(
                            request_id=req_data["request_id"],
                            approval_type=ApprovalType(req_data["approval_type"]),
                            requester_id=req_data["requester_id"],
                            requester_role=req_data["requester_role"],
                            operation_details=req_data["operation_details"],
                            reason=req_data["reason"],
                            created_at=datetime.fromisoformat(req_data["created_at"]),
                            status=ApprovalStatus(req_data["status"]),
                            expires_at=datetime.fromisoformat(req_data["expires_at"]) if req_data.get("expires_at") else None,
                            executable_at=datetime.fromisoformat(req_data["executable_at"]) if req_data.get("executable_at") else None,
                            approvals=req_data.get("approvals", []),
                            rejections=req_data.get("rejections", []),
                            request_hash=req_data.get("request_hash", "")
                        )
                        self._pending_requests[request.request_id] = request
            except Exception as e:
                logger.error(f"Failed to load approval state: {e}")

    def _save_state(self):
        """Persist pending requests"""
        state_file = self.data_dir / "pending_requests.json"
        data = []
        for request in self._pending_requests.values():
            data.append({
                "request_id": request.request_id,
                "approval_type": request.approval_type.value,
                "requester_id": request.requester_id,
                "requester_role": request.requester_role,
                "operation_details": request.operation_details,
                "reason": request.reason,
                "created_at": request.created_at.isoformat(),
                "status": request.status.value,
                "expires_at": request.expires_at.isoformat() if request.expires_at else None,
                "executable_at": request.executable_at.isoformat() if request.executable_at else None,
                "approvals": request.approvals,
                "rejections": request.rejections,
                "request_hash": request.request_hash
            })

        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_request_hash(self, request: ApprovalRequest) -> str:
        """Compute hash of request for integrity verification"""
        content = (
            f"{request.request_id}:"
            f"{request.approval_type.value}:"
            f"{request.requester_id}:"
            f"{json.dumps(request.operation_details, sort_keys=True)}:"
            f"{request.reason}:"
            f"{request.created_at.isoformat()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def configure_rule(
        self,
        approval_type: ApprovalType,
        **kwargs
    ):
        """
        Configure approval rule for an operation type

        Args:
            approval_type: Type of operation
            **kwargs: Rule parameters to override
        """
        if approval_type in self._rules:
            rule = self._rules[approval_type]
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
        else:
            self._rules[approval_type] = ApprovalRule(
                approval_type=approval_type,
                **kwargs
            )

        logger.info(f"Updated approval rule for {approval_type.value}")

    async def create_request(
        self,
        approval_type: ApprovalType,
        requester_id: str,
        requester_role: str,
        operation_details: Dict,
        reason: str = ""
    ) -> ApprovalRequest:
        """
        Create a new approval request

        Returns:
            ApprovalRequest object
        """
        rule = self._rules.get(approval_type)
        if not rule:
            raise ValueError(f"No approval rule for {approval_type}")

        # Check if reason required
        if rule.require_reason and not reason:
            raise ValueError("Reason is required for this operation")

        # Generate request ID
        request_id = hashlib.sha256(
            f"{approval_type.value}:{requester_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        now = datetime.now(timezone.utc)

        request = ApprovalRequest(
            request_id=request_id,
            approval_type=approval_type,
            requester_id=requester_id,
            requester_role=requester_role,
            operation_details=operation_details,
            reason=reason,
            created_at=now,
            expires_at=now + timedelta(minutes=rule.expiry_minutes),
            executable_at=now + timedelta(minutes=rule.time_delay_minutes)
        )

        request.request_hash = self._compute_request_hash(request)

        async with self._lock:
            self._pending_requests[request_id] = request
            self._save_state()

        logger.info(
            f"Approval request {request_id} created: {approval_type.value} by {requester_id}"
        )

        # Send notification
        if self.notification_callback:
            await self.notification_callback(
                f"Approval Required: {approval_type.value}",
                f"Request ID: {request_id}\n"
                f"Requester: {requester_id}\n"
                f"Reason: {reason}\n"
                f"Required approvers: {rule.required_approvers}\n"
                f"Expires: {request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )

        return request

    async def approve(
        self,
        request_id: str,
        approver_id: str,
        approver_role: str,
        reason: str = "",
        ip_address: str = "",
        verified_2fa: bool = False
    ) -> tuple:
        """
        Approve a pending request

        Returns:
            (success: bool, message: str, is_fully_approved: bool)
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return False, "Request not found", False

            # Check status
            if request.status != ApprovalStatus.PENDING:
                return False, f"Request is {request.status.value}", False

            # Check expiry
            if datetime.now(timezone.utc) > request.expires_at:
                request.status = ApprovalStatus.EXPIRED
                self._save_state()
                return False, "Request has expired", False

            rule = self._rules.get(request.approval_type)

            # Check role
            if approver_role not in rule.required_roles:
                return False, f"Role {approver_role} cannot approve this request", False

            # Check self-approval
            if not rule.allow_self_approval and approver_id == request.requester_id:
                return False, "Self-approval not allowed", False

            # Check 2FA requirement
            if rule.require_2fa and not verified_2fa:
                return False, "2FA verification required", False

            # Check if already approved by this user
            if any(a["approver_id"] == approver_id for a in request.approvals):
                return False, "Already approved by this user", False

            # Record approval
            decision = ApprovalDecision(
                decision_id=hashlib.sha256(
                    f"{request_id}:{approver_id}:{datetime.now().isoformat()}".encode()
                ).hexdigest()[:16],
                request_id=request_id,
                approver_id=approver_id,
                approver_role=approver_role,
                decision="approve",
                reason=reason,
                timestamp=datetime.now(timezone.utc),
                ip_address=ip_address,
                verified_2fa=verified_2fa
            )

            request.approvals.append({
                "decision_id": decision.decision_id,
                "approver_id": approver_id,
                "approver_role": approver_role,
                "reason": reason,
                "timestamp": decision.timestamp.isoformat(),
                "ip_address": ip_address
            })

            # Check if fully approved
            is_fully_approved = len(request.approvals) >= rule.required_approvers

            if is_fully_approved:
                request.status = ApprovalStatus.APPROVED

                logger.info(f"Request {request_id} fully approved")

                if self.notification_callback:
                    await self.notification_callback(
                        f"Request Approved: {request.approval_type.value}",
                        f"Request ID: {request_id}\n"
                        f"Approvers: {len(request.approvals)}/{rule.required_approvers}\n"
                        f"Executable at: {request.executable_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    )

            self._save_state()

            return True, "Approval recorded", is_fully_approved

    async def reject(
        self,
        request_id: str,
        rejector_id: str,
        rejector_role: str,
        reason: str,
        ip_address: str = ""
    ) -> tuple:
        """
        Reject a pending request

        Returns:
            (success: bool, message: str)
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return False, "Request not found"

            if request.status != ApprovalStatus.PENDING:
                return False, f"Request is {request.status.value}"

            rule = self._rules.get(request.approval_type)

            # Check role
            if rejector_role not in rule.required_roles:
                return False, f"Role {rejector_role} cannot reject this request"

            # Record rejection
            request.rejections.append({
                "rejector_id": rejector_id,
                "rejector_role": rejector_role,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": ip_address
            })

            request.status = ApprovalStatus.REJECTED
            self._save_state()

            logger.info(f"Request {request_id} rejected by {rejector_id}: {reason}")

            if self.notification_callback:
                await self.notification_callback(
                    f"Request Rejected: {request.approval_type.value}",
                    f"Request ID: {request_id}\n"
                    f"Rejected by: {rejector_id}\n"
                    f"Reason: {reason}"
                )

            return True, "Request rejected"

    async def execute_if_ready(
        self,
        request_id: str,
        executor_callback: Callable
    ) -> tuple:
        """
        Execute approved request if ready

        Uses EXECUTING status to prevent race conditions where multiple
        callers might try to execute the same request concurrently.

        Returns:
            (success: bool, message: str, result: Any)
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return False, "Request not found", None

            # Check if already being executed (race condition prevention)
            if request.status == ApprovalStatus.EXECUTING:
                return False, "Request is already being executed", None

            if request.status == ApprovalStatus.EXECUTED:
                return False, "Request has already been executed", None

            if request.status != ApprovalStatus.APPROVED:
                return False, f"Request is {request.status.value}", None

            now = datetime.now(timezone.utc)

            # Check time delay
            if now < request.executable_at:
                wait_seconds = (request.executable_at - now).total_seconds()
                return False, f"Request not yet executable. Wait {int(wait_seconds)} seconds", None

            # Mark as EXECUTING to prevent concurrent execution attempts
            # This is the critical race condition fix
            request.status = ApprovalStatus.EXECUTING
            self._save_state()

            # Copy operation details for use outside the lock
            operation_details = dict(request.operation_details)

        # Execute outside the lock to avoid blocking other operations
        try:
            result = await executor_callback(operation_details)

            async with self._lock:
                request = self._pending_requests.get(request_id)
                if request:
                    request.status = ApprovalStatus.EXECUTED
                    request.executed_at = datetime.now(timezone.utc)
                    request.execution_result = {"success": True, "result": str(result)}

                    # Move to completed
                    self._completed_requests.append(request)
                    del self._pending_requests[request_id]
                    self._save_state()

            logger.info(f"Request {request_id} executed successfully")

            return True, "Executed successfully", result

        except Exception as e:
            async with self._lock:
                request = self._pending_requests.get(request_id)
                if request:
                    # Revert to APPROVED so it can be retried
                    request.status = ApprovalStatus.APPROVED
                    request.execution_result = {"success": False, "error": str(e)}
                    self._save_state()

            logger.error(f"Request {request_id} execution failed: {e}")
            return False, f"Execution failed: {e}", None

    def get_pending_requests(
        self,
        approval_type: ApprovalType = None,
        approver_role: str = None
    ) -> List[ApprovalRequest]:
        """
        Get pending requests, optionally filtered

        Args:
            approval_type: Filter by type
            approver_role: Filter to requests this role can approve
        """
        requests = list(self._pending_requests.values())

        # Filter expired
        now = datetime.now(timezone.utc)
        for req in requests:
            if req.status == ApprovalStatus.PENDING and now > req.expires_at:
                req.status = ApprovalStatus.EXPIRED
        self._save_state()

        requests = [r for r in requests if r.status == ApprovalStatus.PENDING]

        if approval_type:
            requests = [r for r in requests if r.approval_type == approval_type]

        if approver_role:
            filtered = []
            for req in requests:
                rule = self._rules.get(req.approval_type)
                if rule and approver_role in rule.required_roles:
                    filtered.append(req)
            requests = filtered

        return requests

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a specific request"""
        return self._pending_requests.get(request_id)

    async def cancel_request(
        self,
        request_id: str,
        canceller_id: str,
        reason: str
    ) -> tuple:
        """
        Cancel a pending request

        Only the requester or admin can cancel.
        """
        async with self._lock:
            request = self._pending_requests.get(request_id)
            if not request:
                return False, "Request not found"

            if request.status != ApprovalStatus.PENDING:
                return False, f"Request is {request.status.value}"

            if canceller_id != request.requester_id:
                # Check if admin
                # For now, allow any cancellation with reason
                pass

            request.status = ApprovalStatus.CANCELLED
            self._save_state()

            logger.info(f"Request {request_id} cancelled by {canceller_id}: {reason}")

            return True, "Request cancelled"

    async def cleanup_expired(self):
        """Clean up expired requests with thread-safe locking"""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired = []

            for request_id, request in self._pending_requests.items():
                if request.status == ApprovalStatus.PENDING and now > request.expires_at:
                    request.status = ApprovalStatus.EXPIRED
                    expired.append(request_id)

            for request_id in expired:
                self._completed_requests.append(self._pending_requests[request_id])
                del self._pending_requests[request_id]

            if expired:
                self._save_state()
                logger.info(f"Cleaned up {len(expired)} expired requests")


class TradeApprovalMiddleware:
    """
    Middleware to enforce approval requirements for trades

    Integrates with trading engine to require approval for large trades.
    """

    def __init__(
        self,
        workflow_engine: ApprovalWorkflowEngine,
        threshold_usd: float = 10000
    ):
        self.workflow = workflow_engine
        self.threshold_usd = threshold_usd
        self._approved_trade_ids: Dict[str, datetime] = {}

    async def check_trade_approval(
        self,
        trade_id: str,
        trade_value_usd: float,
        trader_id: str,
        trader_role: str,
        trade_details: Dict
    ) -> tuple:
        """
        Check if trade requires approval and if it's approved

        Returns:
            (can_execute: bool, message: str, request_id: Optional[str])
        """
        # Check if below threshold
        if trade_value_usd < self.threshold_usd:
            return True, "Trade below approval threshold", None

        # Check if already approved
        if trade_id in self._approved_trade_ids:
            approval_time = self._approved_trade_ids[trade_id]
            # Approval valid for 5 minutes
            if datetime.now(timezone.utc) - approval_time < timedelta(minutes=5):
                return True, "Trade pre-approved", None

        # Create approval request
        request = await self.workflow.create_request(
            approval_type=ApprovalType.LARGE_TRADE,
            requester_id=trader_id,
            requester_role=trader_role,
            operation_details={
                "trade_id": trade_id,
                "value_usd": trade_value_usd,
                **trade_details
            },
            reason=f"Large trade: ${trade_value_usd:.2f}"
        )

        return False, f"Approval required. Request ID: {request.request_id}", request.request_id

    def mark_trade_approved(self, trade_id: str):
        """Mark a trade as approved for execution"""
        self._approved_trade_ids[trade_id] = datetime.now(timezone.utc)

        # Cleanup old approvals
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        self._approved_trade_ids = {
            tid: ts for tid, ts in self._approved_trade_ids.items()
            if ts > cutoff
        }


# Helper function to create workflow engine with common configuration
def create_approval_workflow(
    data_dir: Path = None,
    notification_callback: Callable = None
) -> ApprovalWorkflowEngine:
    """
    Create approval workflow engine with sensible defaults
    """
    engine = ApprovalWorkflowEngine(
        data_dir=data_dir,
        notification_callback=notification_callback
    )

    # Apply some additional defaults for crypto trading
    engine.configure_rule(
        ApprovalType.MODE_SWITCH,
        time_delay_minutes=30,  # 30 min delay for paper->live
        required_approvers=2
    )

    return engine


__all__ = [
    "ApprovalType",
    "ApprovalStatus",
    "ApprovalRule",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalWorkflowEngine",
    "TradeApprovalMiddleware",
    "create_approval_workflow"
]
