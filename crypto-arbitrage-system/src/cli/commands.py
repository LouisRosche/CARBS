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

import yaml

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

        if args.mode == 'live':
            confirm = input("\n⚠ LIVE TRADING - Enter 'CONFIRM' to proceed: ")
            if confirm != 'CONFIRM':
                print("Aborted")
                return

        try:
            from ..advanced_main import AdvancedArbitrageBot
        except ImportError:
            print("Error: Could not import AdvancedArbitrageBot. Check installation.")
            return

        # Write PID file for stop/status commands
        pid_file = Path('data/.bot.pid')
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))

        # Remove any stale stop signal
        stop_file = Path('data/.stop_signal')
        if stop_file.exists():
            stop_file.unlink()

        try:
            bot = AdvancedArbitrageBot()
            await bot.run()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            if pid_file.exists():
                pid_file.unlink()

    async def _handle_stop(self, args):
        """Stop trading bot by writing a stop signal file"""
        stop_file = Path('data/.stop_signal')
        pid_file = Path('data/.bot.pid')

        if not pid_file.exists():
            print("\nBot does not appear to be running (no PID file)")
            return

        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stop")
        print("\nStop signal sent. Bot will shut down gracefully.")

    async def _handle_status(self, args):
        """Show quick status from PID file and state manager"""
        print("\n=== CARBS Status ===")

        pid_file = Path('data/.bot.pid')
        if pid_file.exists():
            pid = pid_file.read_text().strip()
            # Check if process is actually running
            try:
                os.kill(int(pid), 0)
                print(f"Status: Running (PID {pid})")
            except (OSError, ValueError):
                print("Status: Stale PID file (bot not running)")
                pid_file.unlink(missing_ok=True)
        else:
            print("Status: Stopped")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            state = sm.get_engine_state()
            print(f"Mode: {state.trading_mode}")
            print(f"Active Since: {state.start_time}")
        except Exception:
            print("Mode: Unknown (state manager unavailable)")

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
        """View balances from state manager"""
        print("\n=== Account Balances ===\n")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            balance_state = sm.get_balance_state()

            if not balance_state.exchange_balances:
                print("No balance data available. Is the bot running?")
                return

            print("Exchange      Currency    Available       Locked          Total")
            print("-" * 70)

            for exchange, currencies in balance_state.exchange_balances.items():
                if args.exchange and args.exchange.lower() != exchange.lower():
                    continue
                for currency, amounts in currencies.items():
                    if args.currency and args.currency.upper() != currency.upper():
                        continue
                    avail = amounts.get('available', 0)
                    locked = amounts.get('locked', 0)
                    total = avail + locked
                    print(f"{exchange:<12}  {currency:<10}  {avail:>12,.2f}    {locked:>12,.2f}    {total:>12,.2f}")

        except Exception:
            print("Balance data unavailable. Start the bot with 'carbs start' first.")

    async def _handle_trades(self, args):
        """View trade history from state manager"""
        print(f"\n=== Recent Trades (Last {args.limit}) ===\n")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            perf_state = sm.get_performance_state()

            trades = perf_state.recent_trades[-args.limit:]
            if not trades:
                print("No trades recorded. Start the bot with 'carbs start' first.")
                return

            print("Time                 Exchange  Symbol    Side   Price       Qty         P&L")
            print("-" * 85)
            for t in trades:
                ex = t.get('exchange', '?')
                sym = t.get('symbol', '?')
                if args.exchange and args.exchange.lower() != ex.lower():
                    continue
                if args.symbol and args.symbol.upper() != sym.upper():
                    continue
                print(f"{t.get('time', '?'):<20} {ex:<8}  {sym:<8}  "
                      f"{t.get('side', '?'):<5}  {t.get('price', '?'):>10}  "
                      f"{t.get('qty', '?'):>10}  {t.get('pnl', '?'):>8}")

        except Exception:
            print("Trade data unavailable. Start the bot with 'carbs start' first.")

    async def _handle_positions(self, args):
        """View open positions from state manager"""
        print("\n=== Open Positions ===\n")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            balance_state = sm.get_balance_state()

            positions = balance_state.open_positions
            if not positions:
                print("No open positions.")
                return

            print("Exchange      Symbol    Quantity      Avg Entry     Current      Unrealized P&L")
            print("-" * 80)
            for p in positions:
                ex = p.get('exchange', '?')
                if args.exchange and args.exchange.lower() != ex.lower():
                    continue
                print(f"{ex:<12}  {p.get('symbol', '?'):<8}  "
                      f"{p.get('quantity', '?'):>10}    {p.get('entry', '?'):>12}  "
                      f"{p.get('current', '?'):>12}  {p.get('pnl', '?'):>14}")

        except Exception:
            print("Position data unavailable. Start the bot with 'carbs start' first.")

    async def _handle_health(self, args):
        """Run actual system health checks"""
        print("\n=== System Health ===\n")

        try:
            from ..api.health import HealthChecker, HealthStatus
            checker = HealthChecker()
            health = await checker.check_health()

            for check in health.checks:
                icon = "OK" if check.status == HealthStatus.HEALTHY else \
                       "WARN" if check.status == HealthStatus.DEGRADED else "FAIL"
                if args.verbose:
                    print(f"  [{icon:4}] {check.name:<15} - {check.message} ({check.duration_ms:.0f}ms)")
                else:
                    print(f"  [{icon:4}] {check.name}")

            print(f"\nOverall: {health.status.value.upper()}")

        except Exception as e:
            logger.debug(f"Health check error: {e}")
            # Fallback: basic system checks
            import psutil
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            print(f"  [{'OK':4}] Memory - Usage: {mem.percent}%")
            print(f"  [{'OK':4}] Disk   - Usage: {disk.percent}%")
            print(f"  [{'OK':4}] CPU    - Usage: {psutil.cpu_percent()}%")
            print(f"\nOverall: BASIC (full checks require running bot)")

    async def _handle_config(self, args):
        """Configuration management — reads actual config file"""
        if not args.config_action:
            print("Usage: carbs config {show|validate|set}")
            return

        config_path = Path('config/config.yaml')

        if args.config_action == 'show':
            if not config_path.exists():
                print(f"Config file not found: {config_path}")
                return

            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)

            print("\n=== Current Configuration ===\n")
            # Pretty-print the actual config
            yaml.dump(config, sys.stdout, default_flow_style=False, indent=2)

        elif args.config_action == 'validate':
            print("\nValidating configuration...")
            try:
                from ..config.settings import load_config
                load_config(str(config_path))
                print("  Configuration is valid")
            except Exception as e:
                print(f"  Validation failed: {e}")

        elif args.config_action == 'set':
            print(f"\nSetting {args.key} = {args.value}")
            print("Note: Use 'config/config.yaml' directly for persistent changes.")
            print("Runtime config changes are not yet supported.")

    async def _handle_opportunities(self, args):
        """View arbitrage opportunities from state manager"""
        print(f"\n=== Arbitrage Opportunities (min spread: {args.min_spread} bps) ===\n")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            engine_state = sm.get_engine_state()

            opps = engine_state.recent_opportunities
            if not opps:
                print("No opportunities detected. Is the bot running?")
                return

            print("Symbol    Buy Exchange   Sell Exchange  Buy Price    Sell Price   Spread   Score")
            print("-" * 85)

            for opp in opps:
                spread = opp.get('spread_bps', 0)
                sym = opp.get('symbol', '?')
                if args.symbol and args.symbol.upper() != sym.upper():
                    continue
                if spread < args.min_spread:
                    continue
                print(f"{sym:<8}  {opp.get('buy_exchange', '?'):<13}  "
                      f"{opp.get('sell_exchange', '?'):<13}  "
                      f"{opp.get('buy_price', '?'):>10}   "
                      f"{opp.get('sell_price', '?'):>10}   "
                      f"{spread:>5.2f}    {opp.get('score', '?')}")

        except Exception:
            print("Opportunity data unavailable. Start the bot with 'carbs start' first.")

    async def _handle_metrics(self, args):
        """View system metrics from state manager"""
        print(f"\n=== System Metrics ({args.period}) ===\n")

        try:
            from ..core.state_manager import get_state_manager
            sm = get_state_manager()
            perf = sm.get_performance_state()

            print("Trading Performance:")
            print(f"  Total Trades: {perf.total_trades}")
            print(f"  Successful: {perf.successful_trades}")
            print(f"  Failed: {perf.failed_trades}")
            print(f"  Net P&L: ${perf.total_pnl:,.2f}")

            engine = sm.get_engine_state()
            print(f"\nSystem:")
            print(f"  Uptime: {engine.uptime_seconds / 3600:.1f}h")
            print(f"  Circuit Breaker Trips: {engine.circuit_breaker_trips}")

        except Exception:
            print("Metrics unavailable. Start the bot with 'carbs start' first.")

    async def _handle_backtest(self, args):
        """Run backtest using the backtest engine"""
        print(f"\n=== Running Backtest ===")
        print(f"Symbol: {args.symbol}")
        print(f"Period: {args.start} to {args.end}")

        try:
            from ..backtest.engine import BacktestEngine
            from ..backtest.models import BacktestConfig
        except ImportError:
            print("\nError: Backtest module not available. Check installation.")
            return

        print("\nLoading historical data...")
        try:
            engine = BacktestEngine()
            results = await engine.run(
                symbol=args.symbol,
                start_date=args.start,
                end_date=args.end,
            )

            print(f"\n--- Backtest Results ---")
            print(f"Total Trades: {results.total_trades}")
            print(f"Win Rate: {results.win_rate:.1%}")
            print(f"Net P&L: ${results.net_pnl:,.2f}")
            print(f"Max Drawdown: {results.max_drawdown:.1%}")
            print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")

        except Exception as e:
            print(f"\nBacktest failed: {e}")


async def _async_main():
    """Async CLI handler"""
    handler = CommandHandler()
    await handler.handle()


def main():
    """Sync CLI entry point (used by console_scripts in pyproject.toml)"""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
