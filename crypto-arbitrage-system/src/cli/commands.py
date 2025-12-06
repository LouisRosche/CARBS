"""
CLI Command Handler

Provides command-line interface for:
- Setup and initialization
- Credential management
- System control
- Quick status checks
"""

import os
import sys
import asyncio
import argparse
import getpass
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Command-line argument handler for CARBS

    Usage:
        carbs setup         # Initial setup wizard
        carbs status        # Quick status check
        carbs start         # Start trading bot
        carbs stop          # Stop trading bot
        carbs dashboard     # Launch interactive dashboard
        carbs creds add     # Add exchange credentials
        carbs creds list    # List configured exchanges
        carbs audit         # View recent audit logs
    """

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser"""
        parser = argparse.ArgumentParser(
            prog='carbs',
            description='CARBS - Crypto ARBitrage System',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  carbs setup                 Initial setup wizard
  carbs dashboard             Launch secure dashboard
  carbs start --mode paper    Start in paper trading mode
  carbs start --mode live     Start in live trading mode
  carbs stop                  Stop the trading bot
  carbs status                Show system status
  carbs creds add binance     Add Binance API credentials
  carbs creds list            List configured exchanges
  carbs audit --limit 50      Show last 50 audit events
            """
        )

        subparsers = parser.add_subparsers(dest='command', help='Commands')

        # Setup command
        setup_parser = subparsers.add_parser('setup', help='Initial setup wizard')
        setup_parser.add_argument(
            '--force', action='store_true',
            help='Force re-setup even if already configured'
        )

        # Dashboard command
        subparsers.add_parser('dashboard', help='Launch interactive dashboard')

        # Start command
        start_parser = subparsers.add_parser('start', help='Start trading bot')
        start_parser.add_argument(
            '--mode', choices=['paper', 'live'], default='paper',
            help='Trading mode (default: paper)'
        )
        start_parser.add_argument(
            '--config', type=str, default='config/config.yaml',
            help='Config file path'
        )

        # Stop command
        subparsers.add_parser('stop', help='Stop trading bot')

        # Status command
        subparsers.add_parser('status', help='Show system status')

        # Credentials command
        creds_parser = subparsers.add_parser('creds', help='Manage credentials')
        creds_sub = creds_parser.add_subparsers(dest='creds_action')

        creds_add = creds_sub.add_parser('add', help='Add exchange credentials')
        creds_add.add_argument('exchange', help='Exchange name (binance, coinbase, etc.)')

        creds_sub.add_parser('list', help='List configured exchanges')

        creds_remove = creds_sub.add_parser('remove', help='Remove credentials')
        creds_remove.add_argument('exchange', help='Exchange name')

        # Audit command
        audit_parser = subparsers.add_parser('audit', help='View audit logs')
        audit_parser.add_argument(
            '--limit', type=int, default=20,
            help='Number of events to show'
        )
        audit_parser.add_argument(
            '--category', type=str,
            help='Filter by category (auth, trade, config, security, system)'
        )

        # User management command
        user_parser = subparsers.add_parser('user', help='User management')
        user_sub = user_parser.add_subparsers(dest='user_action')

        user_add = user_sub.add_parser('add', help='Add user')
        user_add.add_argument('username', help='Username')
        user_add.add_argument(
            '--role', choices=['viewer', 'analyst', 'trader', 'admin'],
            default='viewer', help='User role'
        )

        user_sub.add_parser('list', help='List users')

        # Emergency stop command
        emergency_parser = subparsers.add_parser('emergency', help='Emergency controls')
        emergency_parser.add_argument(
            'action', choices=['stop', 'resume', 'status'],
            help='Emergency action'
        )
        emergency_parser.add_argument(
            '--reason', type=str,
            help='Reason for emergency stop'
        )

        return parser

    async def handle(self, args: Optional[list] = None):
        """Handle command-line arguments"""
        parsed = self.parser.parse_args(args)

        if not parsed.command:
            self.parser.print_help()
            return

        # Route to appropriate handler
        handlers = {
            'setup': self._handle_setup,
            'dashboard': self._handle_dashboard,
            'start': self._handle_start,
            'stop': self._handle_stop,
            'status': self._handle_status,
            'creds': self._handle_creds,
            'audit': self._handle_audit,
            'user': self._handle_user,
            'emergency': self._handle_emergency
        }

        handler = handlers.get(parsed.command)
        if handler:
            await handler(parsed)
        else:
            print(f"Unknown command: {parsed.command}")
            self.parser.print_help()

    async def _handle_setup(self, args):
        """Initial setup wizard"""
        print("\n=== CARBS Setup Wizard ===\n")

        # Check if already configured
        data_dir = Path('data')
        if (data_dir / '.users.json').exists() and not args.force:
            print("System already configured. Use --force to re-setup.")
            return

        # Create directories
        dirs = ['data', 'data/logs', 'data/audit']
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            print(f"✓ Created {d}/")

        # Generate master key
        print("\n--- Encryption Setup ---")
        master_key = os.getenv('CARBS_MASTER_KEY')
        if not master_key:
            import secrets
            master_key = secrets.token_urlsafe(32)
            print(f"\nGenerated master key (save this securely!):")
            print(f"  CARBS_MASTER_KEY={master_key}")
            print("\nAdd this to your environment or .env file")

            # Save to .env if user wants
            if input("\nSave to .env file? (y/n): ").lower() == 'y':
                with open('.env', 'a') as f:
                    f.write(f"\nCARBS_MASTER_KEY={master_key}\n")
                os.chmod('.env', 0o600)
                print("✓ Saved to .env")

        # Initialize secrets manager
        from security.encryption import SecretsManager
        os.environ['CARBS_MASTER_KEY'] = master_key
        secrets_mgr = SecretsManager(master_key)
        print("✓ Encryption initialized")

        # Create admin user
        print("\n--- Admin Account Setup ---")
        from security.auth import AuthenticationManager

        auth_mgr = AuthenticationManager()
        username = input("Admin username: ")
        password = getpass.getpass("Password (min 12 chars): ")

        if len(password) < 12:
            print("Password too short!")
            return

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Passwords don't match!")
            return

        user = auth_mgr.create_user(username, password, role='super_admin')
        print(f"✓ Admin user '{username}' created")

        # Setup 2FA
        if input("\nEnable 2FA? (recommended) (y/n): ").lower() == 'y':
            uri = auth_mgr.setup_totp(username)
            print(f"\nScan with authenticator app:\n{uri}\n")
            totp = input("Enter 6-digit code: ")
            if auth_mgr.enable_totp(username, totp):
                print("✓ 2FA enabled")
            else:
                print("Invalid code - 2FA not enabled")

        print("\n=== Setup Complete ===")
        print("\nNext steps:")
        print("  1. Add exchange credentials: carbs creds add binance")
        print("  2. Configure settings: edit config/config.yaml")
        print("  3. Start dashboard: carbs dashboard")
        print("  4. Start trading: carbs start --mode paper")

    async def _handle_dashboard(self, args):
        """Launch interactive dashboard"""
        from cli.dashboard import run_dashboard
        await run_dashboard()

    async def _handle_start(self, args):
        """Start trading bot"""
        print(f"\nStarting CARBS in {args.mode} mode...")
        print(f"Config: {args.config}")

        # This would launch the actual bot
        if args.mode == 'live':
            confirm = input("\n⚠ LIVE TRADING - Enter 'CONFIRM' to proceed: ")
            if confirm != 'CONFIRM':
                print("Aborted")
                return

        print("\nBot would start here...")
        print("(Use 'carbs stop' to stop)")

    async def _handle_stop(self, args):
        """Stop trading bot"""
        print("\nStopping CARBS...")
        # This would send stop signal to running bot
        print("Stop signal sent")

    async def _handle_status(self, args):
        """Show quick status"""
        print("\n=== CARBS Status ===")
        print("Status: Stopped")
        print("Mode: Paper")
        print("Last run: Never")
        print("\nUse 'carbs dashboard' for full status")

    async def _handle_creds(self, args):
        """Handle credentials commands"""
        if not args.creds_action:
            print("Usage: carbs creds {add|list|remove}")
            return

        # Need master key
        master_key = os.getenv('CARBS_MASTER_KEY')
        if not master_key:
            master_key = getpass.getpass("Master key: ")

        from security.encryption import SecretsManager

        try:
            secrets_mgr = SecretsManager(master_key)
        except Exception as e:
            print(f"Error: {e}")
            return

        if args.creds_action == 'list':
            secrets = secrets_mgr.list_secrets()
            exchanges = set()
            for s in secrets:
                if s.endswith('_api_key'):
                    exchanges.add(s.replace('_api_key', ''))

            if exchanges:
                print("\nConfigured exchanges:")
                for ex in sorted(exchanges):
                    print(f"  ✓ {ex}")
            else:
                print("\nNo exchanges configured")

        elif args.creds_action == 'add':
            exchange = args.exchange.lower()
            print(f"\nAdding credentials for {exchange}")

            api_key = getpass.getpass("API Key: ")
            secret = getpass.getpass("Secret: ")

            needs_pass = exchange in ['coinbase', 'kucoin', 'okx']
            passphrase = None
            if needs_pass:
                passphrase = getpass.getpass("Passphrase: ")

            secrets_mgr.set_secret(f"{exchange}_api_key", api_key)
            secrets_mgr.set_secret(f"{exchange}_secret", secret)
            if passphrase:
                secrets_mgr.set_secret(f"{exchange}_passphrase", passphrase)

            print(f"✓ Credentials for {exchange} saved")

        elif args.creds_action == 'remove':
            exchange = args.exchange.lower()
            confirm = input(f"Remove {exchange} credentials? (y/n): ")
            if confirm.lower() == 'y':
                secrets_mgr.delete_secret(f"{exchange}_api_key")
                secrets_mgr.delete_secret(f"{exchange}_secret")
                secrets_mgr.delete_secret(f"{exchange}_passphrase")
                print(f"✓ Credentials for {exchange} removed")

    async def _handle_audit(self, args):
        """View audit logs"""
        from security.audit import get_audit_logger, AuditCategory

        audit = get_audit_logger()

        category = None
        if args.category:
            try:
                category = AuditCategory(args.category)
            except ValueError:
                print(f"Invalid category: {args.category}")
                return

        events = audit.query(category=category, limit=args.limit)

        print(f"\n=== Recent Audit Events ({len(events)}) ===\n")

        for event in events:
            status = "✓" if event.success else "✗"
            print(f"{event.timestamp.strftime('%Y-%m-%d %H:%M:%S')} "
                  f"[{event.category.value}] {status} "
                  f"{event.action} by {event.actor} on {event.resource}")
            if event.error_message:
                print(f"  Error: {event.error_message}")

    async def _handle_user(self, args):
        """Handle user commands"""
        if not args.user_action:
            print("Usage: carbs user {add|list}")
            return

        from security.auth import AuthenticationManager
        auth_mgr = AuthenticationManager()

        if args.user_action == 'list':
            print("\n=== Users ===")
            for user in auth_mgr._users.values():
                mfa = "2FA" if user.totp_enabled else ""
                print(f"  {user.username} ({user.role}) {mfa}")

        elif args.user_action == 'add':
            password = getpass.getpass("Password: ")
            if len(password) < 12:
                print("Password must be at least 12 characters")
                return

            user = auth_mgr.create_user(args.username, password, role=args.role)
            print(f"✓ User {args.username} created with role {args.role}")

    async def _handle_emergency(self, args):
        """Handle emergency commands"""
        from security.access_control import AccessControl, EmergencyControls

        ac = AccessControl()
        ec = EmergencyControls(ac)

        if args.action == 'status':
            status = ec.get_emergency_status()
            if status['is_active']:
                print("\n⚠ EMERGENCY STOP IS ACTIVE")
                print(f"  Reason: {status['reason']}")
                print(f"  Activated by: {status['activated_by']}")
            else:
                print("\n✓ System operating normally")

        elif args.action == 'stop':
            if not args.reason:
                print("Error: --reason required")
                return

            print("\n⚠ ACTIVATING EMERGENCY STOP")
            confirm = input("Enter 'EMERGENCY' to confirm: ")
            if confirm != 'EMERGENCY':
                print("Aborted")
                return

            ec.activate_emergency_stop(
                username='cli',
                role='admin',
                reason=args.reason,
                ip_address='localhost'
            )
            print("EMERGENCY STOP ACTIVATED")

        elif args.action == 'resume':
            print("\nDeactivating emergency stop...")
            confirm = input("Enter 'RESUME' to confirm: ")
            if confirm != 'RESUME':
                print("Aborted")
                return

            ec.deactivate_emergency_stop(
                username='cli',
                role='admin',
                ip_address='localhost'
            )
            print("Emergency stop deactivated")


async def main():
    """CLI entry point"""
    handler = CommandHandler()
    await handler.handle()


if __name__ == "__main__":
    asyncio.run(main())
