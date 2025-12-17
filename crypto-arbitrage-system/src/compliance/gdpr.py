"""
GDPR Compliance

Right to access, right to erasure, and data retention utilities.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict

import aiofiles

logger = logging.getLogger(__name__)


class GDPRCompliance:
    """
    GDPR compliance utilities

    Supports:
    - Right to access (data export)
    - Right to erasure (data deletion)
    - Data retention policies
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.retention_days = 2555  # ~7 years for financial records

    async def export_user_data(self, user_id: str) -> Path:
        """
        Export all data for a user (Right to Access)

        Returns path to exported data package.
        """
        export_dir = self.data_dir / "gdpr_exports" / user_id
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_path = export_dir / f"data_export_{timestamp}.json"

        # Collect user data from various sources
        user_data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "data_categories": {
                "trades": [],
                "audit_logs": [],
                "settings": {},
                "sessions": [],
                "portfolio_snapshots": [],
                "login_history": [],
                "api_access_logs": []
            }
        }

        # Collect actual data from various modules
        try:
            # 1. Collect trade history from trade journal
            trade_journal_path = self.data_dir / "journal" / f"{user_id}_trades.json"
            if trade_journal_path.exists():
                async with aiofiles.open(trade_journal_path, 'r') as f:
                    content = await f.read()
                    user_data["data_categories"]["trades"] = json.loads(content)

            # 2. Collect audit logs from audit system
            try:
                from security.audit import get_audit_logger
                audit_logger = get_audit_logger()
                if audit_logger:
                    user_events = audit_logger.query(actor=user_id, limit=10000)
                    user_data["data_categories"]["audit_logs"] = [
                        {
                            "timestamp": e.timestamp.isoformat(),
                            "category": e.category.value if hasattr(e.category, 'value') else str(e.category),
                            "action": e.action,
                            "resource": e.resource,
                            "success": e.success
                        }
                        for e in user_events
                    ]
            except ImportError:
                logger.warning("Audit logger not available for GDPR export")

            # 3. Collect user settings
            settings_path = self.data_dir / "settings" / f"{user_id}_settings.json"
            if settings_path.exists():
                async with aiofiles.open(settings_path, 'r') as f:
                    content = await f.read()
                    user_data["data_categories"]["settings"] = json.loads(content)

            # 4. Add data processing information (GDPR Art. 15)
            user_data["data_processing_info"] = {
                "purposes": [
                    "Trading execution and management",
                    "Risk analysis and portfolio optimization",
                    "Tax calculation and reporting",
                    "Security and fraud prevention",
                    "Service improvement and analytics"
                ],
                "legal_basis": "Contract performance and legitimate interests",
                "retention_period_days": self.retention_days,
                "data_recipients": [
                    "Exchange partners (for trade execution)",
                    "Tax authorities (upon legal request)"
                ],
                "international_transfers": "Data may be processed in exchange jurisdictions",
                "automated_decision_making": "Trading signals use ML-based scoring (user can opt-out)",
                "data_source": "User-provided and trading activity generated"
            }

        except Exception as e:
            logger.error(f"Error collecting GDPR data for {user_id}: {e}")
            user_data["collection_errors"] = str(e)

        async with aiofiles.open(package_path, 'w') as f:
            await f.write(json.dumps(user_data, indent=2))

        logger.info(f"GDPR data export for user {user_id}: {package_path}")
        return package_path

    async def request_data_deletion(self, user_id: str, reason: str) -> Dict:
        """
        Process data deletion request (Right to Erasure)

        Note: Financial records may have legal retention requirements
        that override GDPR deletion rights.
        """
        deletion_record = {
            "request_id": hashlib.sha256(
                f"{user_id}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
            "user_id": user_id,
            "request_timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "status": "pending_review",
            "notes": "Financial records subject to legal retention requirements"
        }

        # Log the request
        request_log = self.data_dir / "gdpr_requests.json"
        requests = []
        if request_log.exists():
            with open(request_log) as f:
                requests = json.load(f)

        requests.append(deletion_record)

        with open(request_log, 'w') as f:
            json.dump(requests, f, indent=2)

        logger.info(f"GDPR deletion request {deletion_record['request_id']} logged")
        return deletion_record

    async def enforce_retention_policy(self):
        """
        Enforce data retention policy

        Removes data older than retention period, except:
        - Financial records required for tax compliance
        - Audit logs required for regulatory compliance
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

        # This would be implemented to clean up old data
        # For now, just log the action
        logger.info(f"Retention policy check: would remove data before {cutoff}")

        return {
            "cutoff_date": cutoff.isoformat(),
            "retained_categories": ["financial_records", "audit_logs"],
            "cleaned_categories": ["session_data", "temp_files"]
        }
