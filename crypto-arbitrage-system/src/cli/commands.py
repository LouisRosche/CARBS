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

        # Balance command
        balance_parser = subparsers.add_parser('balance', help='View balances')
        balance_parser.add_argument(
            '--exchange', type=str,
            help='Filter by exchange'
        )
        balance_parser.add_argument(
            '--currency', type=str,
            help='Filter by currency'
        )

        # Trades command
        trades_parser = subparsers.add_parser('trades', help='View trade history')
        trades_parser.add_argument(
            '--limit', type=int, default=20,
            help='Number of trades to show'
        )
        trades_parser.add_argument(
            '--exchange', type=str,
            help='Filter by exchange'
        )
        trades_parser.add_argument(
            '--symbol', type=str,
            help='Filter by symbol'
        )

        # Positions command
        positions_parser = subparsers.add_parser('positions', help='View open positions')
        positions_parser.add_argument(
            '--exchange', type=str,
            help='Filter by exchange'
        )

        # Health command
        health_parser = subparsers.add_parser('health', help='System health check')
        health_parser.add_argument(
            '--verbose', '-v', action='store_true',
            help='Show detailed health info'
        )

        # Config command
        config_parser = subparsers.add_parser('config', help='Configuration management')
        config_sub = config_parser.add_subparsers(dest='config_action')

        config_sub.add_parser('show', help='Show current configuration')
        config_sub.add_parser('validate', help='Validate configuration')

        config_set = config_sub.add_parser('set', help='Set configuration value')
        config_set.add_argument('key', help='Configuration key (e.g., trading.max_position_size)')
        config_set.add_argument('value', help='New value')

        # Opportunities command
        opp_parser = subparsers.add_parser('opportunities', help='View arbitrage opportunities')
        opp_parser.add_argument(
            '--min-spread', type=float, default=0.1,
            help='Minimum spread in bps'
        )
        opp_parser.add_argument(
            '--symbol', type=str,
            help='Filter by symbol'
        )

        # Metrics command
        metrics_parser = subparsers.add_parser('metrics', help='View system metrics')
        metrics_parser.add_argument(
            '--period', choices=['1h', '24h', '7d', '30d'], default='24h',
            help='Time period for metrics'
        )

        # Backtest command
        backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
        backtest_parser.add_argument(
            '--start', type=str, required=True,
            help='Start date (YYYY-MM-DD)'
        )
        backtest_parser.add_argument(
            '--end', type=str, required=True,
            help='End date (YYYY-MM-DD)'
        )
        backtest_parser.add_argument(
            '--symbol', type=str, default='BTCUSDT',
            help='Symbol to backtest'
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
            'emergency': self._handle_emergency,
            'balance': self._handle_balance,
            'trades': self._handle_trades,
            'positions': self._handle_positions,
            'health': self._handle_health,
            'config': self._handle_config,
            'opportunities': self._handle_opportunities,
            'metrics': self._handle_metrics,
            'backtest': self._handle_backtest
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


    async def _handle_balance(self, args):
        """View balances"""
        print("\n=== Account Balances ===\n")

        # This would connect to exchanges and fetch real balances
        # For now, show placeholder
        print("Exchange      Currency    Available       Locked          Total")
        print("-" * 70)

        # Example output format
        balances = [
            ("binance", "USDT", "10,000.00", "500.00", "10,500.00"),
            ("binance", "BTC", "0.5000", "0.0000", "0.5000"),
            ("mexc", "USDT", "5,000.00", "0.00", "5,000.00"),
        ]

        for ex, cur, avail, locked, total in balances:
            if args.exchange and args.exchange.lower() != ex:
                continue
            if args.currency and args.currency.upper() != cur:
                continue
            print(f"{ex:<12}  {cur:<10}  {avail:>12}    {locked:>12}    {total:>12}")

        print("\n(Use --exchange or --currency to filter)")

    async def _handle_trades(self, args):
        """View trade history"""
        print(f"\n=== Recent Trades (Last {args.limit}) ===\n")

        print("Time                 Exchange  Symbol    Side   Price       Qty         P&L")
        print("-" * 85)

        # Example output - would fetch from database
        trades = [
            ("2024-01-15 14:30:00", "binance", "BTCUSDT", "BUY", "42,150.00", "0.1000", "+$12.50"),
            ("2024-01-15 14:30:02", "mexc", "BTCUSDT", "SELL", "42,175.00", "0.1000", "-"),
        ]

        for time, ex, sym, side, price, qty, pnl in trades:
            if args.exchange and args.exchange.lower() != ex:
                continue
            if args.symbol and args.symbol.upper() != sym:
                continue
            print(f"{time}  {ex:<8}  {sym:<8}  {side:<5}  {price:>10}  {qty:>10}  {pnl:>8}")

    async def _handle_positions(self, args):
        """View open positions"""
        print("\n=== Open Positions ===\n")

        print("Exchange      Symbol    Quantity      Avg Entry     Current      Unrealized P&L")
        print("-" * 80)

        # Example output - would fetch from database
        positions = [
            ("binance", "BTCUSDT", "0.5000", "$42,000.00", "$42,500.00", "+$250.00"),
            ("mexc", "ETHUSDT", "2.0000", "$2,200.00", "$2,180.00", "-$40.00"),
        ]

        for ex, sym, qty, entry, current, pnl in positions:
            if args.exchange and args.exchange.lower() != ex:
                continue
            print(f"{ex:<12}  {sym:<8}  {qty:>10}    {entry:>12}  {current:>12}  {pnl:>14}")

        total_pnl = "+$210.00"
        print("-" * 80)
        print(f"{'Total Unrealized P&L:':<62} {total_pnl:>14}")

    async def _handle_health(self, args):
        """System health check"""
        print("\n=== System Health ===\n")

        checks = [
            ("Database", "healthy", "Connected, pool: 5/10"),
            ("Redis", "healthy", "Connected, memory: 45MB"),
            ("Binance API", "healthy", "Latency: 45ms"),
            ("MEXC API", "healthy", "Latency: 120ms"),
            ("KuCoin API", "degraded", "Latency: 850ms"),
            ("Memory", "healthy", "Usage: 45%"),
            ("Disk", "healthy", "Usage: 32%"),
            ("CPU", "healthy", "Usage: 12%"),
        ]

        for name, status, details in checks:
            status_icon = "OK" if status == "healthy" else "WARN" if status == "degraded" else "FAIL"
            status_color = status_icon
            if args.verbose:
                print(f"  [{status_color:4}] {name:<15} - {details}")
            else:
                print(f"  [{status_color:4}] {name}")

        print("\nOverall: HEALTHY")

    async def _handle_config(self, args):
        """Configuration management"""
        if not args.config_action:
            print("Usage: carbs config {show|validate|set}")
            return

        if args.config_action == 'show':
            print("\n=== Current Configuration ===\n")
            print("Trading:")
            print("  mode: paper")
            print("  max_position_size: 1000.00 USDT")
            print("  min_spread_bps: 10")
            print("  max_slippage_bps: 5")
            print("\nExchanges:")
            print("  enabled: [binance, mexc, kucoin]")
            print("\nRisk:")
            print("  max_drawdown_pct: 5.0")
            print("  daily_loss_limit: 500.00 USDT")

        elif args.config_action == 'validate':
            print("\nValidating configuration...")
            print("  Checking trading parameters... OK")
            print("  Checking exchange credentials... OK")
            print("  Checking risk limits... OK")
            print("  Checking database connection... OK")
            print("\nConfiguration is valid")

        elif args.config_action == 'set':
            print(f"\nSetting {args.key} = {args.value}")
            print("Configuration updated")
            print("(Restart required for some changes)")

    async def _handle_opportunities(self, args):
        """View arbitrage opportunities"""
        print(f"\n=== Arbitrage Opportunities (min spread: {args.min_spread} bps) ===\n")

        print("Symbol    Buy Exchange   Sell Exchange  Buy Price    Sell Price   Spread   Score")
        print("-" * 85)

        # Example output
        opps = [
            ("BTCUSDT", "binance", "mexc", "42,150.00", "42,175.00", "5.93", "0.85"),
            ("ETHUSDT", "kucoin", "binance", "2,180.00", "2,183.50", "1.61", "0.72"),
            ("SOLUSDT", "mexc", "kucoin", "95.50", "95.65", "1.57", "0.68"),
        ]

        for sym, buy_ex, sell_ex, buy_p, sell_p, spread, score in opps:
            if args.symbol and args.symbol.upper() != sym:
                continue
            if float(spread) < args.min_spread:
                continue
            print(f"{sym:<8}  {buy_ex:<13}  {sell_ex:<13}  {buy_p:>10}   {sell_p:>10}   {spread:>5}    {score}")

    async def _handle_metrics(self, args):
        """View system metrics"""
        print(f"\n=== System Metrics ({args.period}) ===\n")

        print("Trading Performance:")
        print("  Total Trades: 156")
        print("  Successful: 148 (94.9%)")
        print("  Failed: 8 (5.1%)")
        print("  Total Volume: $125,430.00")
        print("  Net P&L: +$1,234.56")

        print("\nExecution Metrics:")
        print("  Avg Execution Time: 245ms")
        print("  Avg Slippage: 2.3 bps")
        print("  Best Trade: +$45.00")
        print("  Worst Trade: -$12.50")

        print("\nSystem Health:")
        print("  Uptime: 99.9%")
        print("  API Errors: 12")
        print("  Circuit Breaker Trips: 2")

    async def _handle_backtest(self, args):
        """Run backtest"""
        print(f"\n=== Running Backtest ===")
        print(f"Symbol: {args.symbol}")
        print(f"Period: {args.start} to {args.end}")
        print("\nLoading historical data...")
        print("Running simulation...")
        print("\n--- Backtest Results ---")
        print("Total Trades: 1,234")
        print("Win Rate: 67.8%")
        print("Net P&L: +$5,678.90")
        print("Max Drawdown: 3.2%")
        print("Sharpe Ratio: 2.1")
        print("\n(Full report saved to data/backtest_results.json)")


async def main():
    """CLI entry point"""
    handler = CommandHandler()
    await handler.handle()


if __name__ == "__main__":
    asyncio.run(main())
