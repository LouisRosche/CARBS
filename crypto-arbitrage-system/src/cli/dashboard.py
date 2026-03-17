"""
Secure CLI Dashboard

Features:
- Real-time trading status
- Portfolio overview
- Risk metrics display
- Secure credential management
- Emergency controls
- Audit log viewer

Uses Rich library for beautiful terminal UI
"""

import os
import sys
import asyncio
import getpass
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..security.auth import AuthenticationManager, Session, AuthError
from ..security.encryption import SecretsManager, EncryptionError
from ..security.audit import AuditLogger, AuditCategory, get_audit_logger
from ..security.access_control import AccessControl, Permission, EmergencyControls

# Import state manager for real-time data
try:
    from ..core.state_manager import StateManager, get_state_manager
    STATE_MANAGER_AVAILABLE = True
except ImportError:
    STATE_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class Dashboard:
    """
    Secure CLI Dashboard for CARBS

    Provides authenticated access to system controls
    """

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.auth_manager: Optional[AuthenticationManager] = None
        self.secrets_manager: Optional[SecretsManager] = None
        self.access_control: Optional[AccessControl] = None
        self.emergency_controls: Optional[EmergencyControls] = None
        self.audit_logger: Optional[AuditLogger] = None
        self.session: Optional[Session] = None
        self.state_manager: Optional['StateManager'] = None

    def _get_system_state(self) -> Dict[str, Any]:
        """Get system state from state manager or return defaults"""
        if STATE_MANAGER_AVAILABLE and self.state_manager:
            try:
                trading_state = self.state_manager.get_trading_state()
                return {
                    'running': trading_state.running,
                    'mode': trading_state.mode,
                    'opportunities_detected': trading_state.opportunities_detected,
                    'opportunities_executed': trading_state.opportunities_executed,
                    'total_profit': float(trading_state.total_profit),
                    'current_capital': float(trading_state.current_capital),
                    'exchanges_connected': trading_state.exchanges_connected,
                    'emergency_stop': trading_state.emergency_stop,
                    'win_rate': trading_state.win_rate,
                    'sharpe_ratio': trading_state.sharpe_ratio,
                    'total_trades': trading_state.total_trades,
                    'successful_trades': trading_state.successful_trades,
                    'failed_trades': trading_state.failed_trades
                }
            except Exception as e:
                logger.warning(f"Failed to get state from manager: {e}")

        # Default state
        return {
            'running': False,
            'mode': 'paper',
            'opportunities_detected': 0,
            'opportunities_executed': 0,
            'total_profit': 0.0,
            'current_capital': 10000.0,
            'exchanges_connected': [],
            'emergency_stop': False,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0
        }

    @property
    def system_state(self) -> Dict[str, Any]:
        """Property to get current system state"""
        return self._get_system_state()

    def _print(self, message: str, style: str = None):
        """Print with or without Rich"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)

    def _input(self, prompt: str) -> str:
        """Get input with or without Rich"""
        if self.console:
            return Prompt.ask(prompt)
        return input(f"{prompt}: ")

    def _password(self, prompt: str) -> str:
        """Get password securely"""
        if self.console:
            return Prompt.ask(prompt, password=True)
        return getpass.getpass(f"{prompt}: ")

    def _confirm(self, prompt: str) -> bool:
        """Get confirmation"""
        if self.console:
            return Confirm.ask(prompt)
        response = input(f"{prompt} (y/n): ")
        return response.lower() in ('y', 'yes')

    async def initialize(self):
        """Initialize all components"""
        self._print("\n[bold blue]CARBS - Crypto ARBitrage System[/bold blue]", "bold")
        self._print("[dim]Secure Trading Dashboard v1.0[/dim]\n")

        # Initialize secrets manager
        try:
            master_key = os.getenv('CARBS_MASTER_KEY')
            if not master_key:
                self._print("[yellow]Master key not found in environment.[/yellow]")
                master_key = self._password("Enter master encryption key")

            self.secrets_manager = SecretsManager(master_key)
            self._print("[green]✓[/green] Encryption initialized")

        except EncryptionError as e:
            self._print(f"[red]✗ Encryption error: {e}[/red]")
            return False

        # Initialize auth manager
        self.auth_manager = AuthenticationManager()
        self._print("[green]✓[/green] Authentication initialized")

        # Initialize access control
        self.access_control = AccessControl()
        self.emergency_controls = EmergencyControls(self.access_control)
        self._print("[green]✓[/green] Access control initialized")

        # Initialize audit logger
        self.audit_logger = get_audit_logger()
        self._print("[green]✓[/green] Audit logging initialized")

        # Initialize state manager for real-time data
        if STATE_MANAGER_AVAILABLE:
            try:
                self.state_manager = get_state_manager()
                self._print("[green]✓[/green] State manager connected")
            except Exception as e:
                self._print(f"[yellow]⚠[/yellow] State manager not available: {e}")
                self.state_manager = None
        else:
            self._print("[yellow]⚠[/yellow] State manager not available - using defaults")

        # Check if any users exist
        if not self.auth_manager._users:
            self._print("\n[yellow]No users configured. Creating initial admin account.[/yellow]")
            await self._setup_initial_admin()

        return True

    async def _setup_initial_admin(self):
        """Setup initial admin account"""
        self._print("\n[bold]Create Admin Account[/bold]")

        username = self._input("Username")
        password = self._password("Password (min 12 chars)")
        password_confirm = self._password("Confirm password")

        if password != password_confirm:
            self._print("[red]Passwords don't match[/red]")
            return await self._setup_initial_admin()

        if len(password) < 12:
            self._print("[red]Password must be at least 12 characters[/red]")
            return await self._setup_initial_admin()

        try:
            user = self.auth_manager.create_user(
                username=username,
                password=password,
                role='super_admin'
            )
            self._print(f"[green]✓[/green] Admin user '{username}' created")

            # Setup 2FA
            if self._confirm("Enable two-factor authentication (recommended)?"):
                uri = self.auth_manager.setup_totp(username)
                self._print("\n[bold]Scan this QR code with your authenticator app:[/bold]")
                self._print(f"[dim]{uri}[/dim]\n")

                totp_token = self._input("Enter the 6-digit code from your app")
                if self.auth_manager.enable_totp(username, totp_token):
                    self._print("[green]✓[/green] 2FA enabled successfully")
                else:
                    self._print("[red]Invalid code. 2FA not enabled.[/red]")

            self.audit_logger.log_security_event(
                action='initial_setup',
                actor='system',
                resource='admin_account',
                details={'username': username}
            )

        except AuthError as e:
            self._print(f"[red]Error: {e}[/red]")
            return await self._setup_initial_admin()

    async def login(self) -> bool:
        """Authenticate user"""
        self._print("\n[bold]Login Required[/bold]")

        max_attempts = 3
        for attempt in range(max_attempts):
            username = self._input("Username")
            password = self._password("Password")

            # Check if 2FA is needed
            user = self.auth_manager.get_user(username)
            totp_token = None
            if user and user.totp_enabled:
                totp_token = self._input("2FA Code")

            try:
                self.session = self.auth_manager.authenticate(
                    username=username,
                    password=password,
                    totp_token=totp_token,
                    ip_address='localhost',
                    user_agent='cli-dashboard'
                )

                self.audit_logger.log_login(
                    username=username,
                    ip_address='localhost',
                    success=True,
                    mfa_used=totp_token is not None
                )

                self._print(f"\n[green]✓[/green] Welcome, {username}!")
                self._print(f"[dim]Role: {self.session.role} | Session expires: {self.session.expires_at}[/dim]\n")
                return True

            except AuthError as e:
                self.audit_logger.log_login(
                    username=username,
                    ip_address='localhost',
                    success=False,
                    error=str(e)
                )
                remaining = max_attempts - attempt - 1
                self._print(f"[red]✗ {e}[/red]")
                if remaining > 0:
                    self._print(f"[dim]{remaining} attempts remaining[/dim]")

        self._print("[red]Too many failed attempts. Please try again later.[/red]")
        return False

    def show_main_menu(self):
        """Display main menu based on user permissions"""
        if not self.console:
            return self._show_simple_menu()

        # Build menu based on permissions
        menu_items = []

        # Always show status
        menu_items.append(("1", "System Status", True))

        # Trading menu
        can_trade = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.TRADE_VIEW
        ).allowed
        if can_trade:
            menu_items.append(("2", "Trading Controls", True))

        # Portfolio
        menu_items.append(("3", "Portfolio & Risk", True))

        # Configuration
        can_config = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.CONFIG_VIEW
        ).allowed
        if can_config:
            menu_items.append(("4", "Configuration", True))

        # Credentials
        can_creds = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.CREDS_VIEW
        ).allowed
        if can_creds:
            menu_items.append(("5", "Credentials", True))

        # Audit logs
        can_audit = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.REPORT_AUDIT
        ).allowed
        if can_audit:
            menu_items.append(("6", "Audit Logs", True))

        # User management (admin only)
        can_users = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.USER_VIEW
        ).allowed
        if can_users:
            menu_items.append(("7", "User Management", True))

        # Emergency controls
        can_emergency = self.access_control.check_permission(
            self.session.username, self.session.role,
            Permission.TRADE_EMERGENCY_STOP
        ).allowed
        if can_emergency:
            menu_items.append(("8", "[red]Emergency Controls[/red]", True))

        menu_items.append(("0", "Logout", True))

        # Display menu
        table = Table(title="Main Menu", show_header=False, box=None)
        for key, label, _ in menu_items:
            table.add_row(f"[bold]{key}[/bold]", label)

        self.console.print(table)
        return {item[0]: item[1] for item in menu_items}

    def _show_simple_menu(self):
        """Simple menu for non-Rich environments"""
        print("\n=== Main Menu ===")
        print("1. System Status")
        print("2. Trading Controls")
        print("3. Portfolio & Risk")
        print("4. Configuration")
        print("5. Credentials")
        print("6. Audit Logs")
        print("7. User Management")
        print("8. Emergency Controls")
        print("0. Logout")
        return {'0': 'Logout', '1': 'Status', '2': 'Trading'}

    def show_system_status(self):
        """Display system status"""
        state = self.system_state

        if not self.console:
            print(f"\nSystem Status:")
            print(f"  Running: {state['running']}")
            print(f"  Mode: {state['mode']}")
            print(f"  Opportunities: {state['opportunities_detected']} detected / {state['opportunities_executed']} executed")
            print(f"  Profit: ${state['total_profit']:.2f}")
            print(f"  Capital: ${state['current_capital']:.2f}")
            print(f"  Win Rate: {state['win_rate']*100:.1f}%")
            print(f"  Sharpe: {state['sharpe_ratio']:.2f}")
            return

        # Emergency status
        if self.emergency_controls.is_emergency_mode or state.get('emergency_stop'):
            status = self.emergency_controls.get_emergency_status()
            self.console.print(Panel(
                f"[bold red]⚠ EMERGENCY STOP ACTIVE[/bold red]\n"
                f"Reason: {status.get('reason', 'Unknown')}\n"
                f"Activated by: {status.get('activated_by', 'System')}",
                border_style="red"
            ))

        # System table
        table = Table(title="System Status", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row(
            "Status",
            "[green]Running[/green]" if state['running'] else "[red]Stopped[/red]"
        )
        table.add_row(
            "Mode",
            "[yellow]Paper[/yellow]" if state['mode'] == 'paper' else "[red]Live[/red]"
        )
        table.add_row("Opportunities Detected", str(state['opportunities_detected']))
        table.add_row("Opportunities Executed", str(state['opportunities_executed']))
        table.add_row("Total Profit", f"${state['total_profit']:.2f}")
        table.add_row("Current Capital", f"${state['current_capital']:.2f}")
        table.add_row(
            "Exchanges",
            ", ".join(state['exchanges_connected']) or "None connected"
        )
        table.add_row("Total Trades", str(state.get('total_trades', 0)))
        table.add_row("Successful/Failed", f"{state.get('successful_trades', 0)}/{state.get('failed_trades', 0)}")
        table.add_row("Win Rate", f"{state.get('win_rate', 0)*100:.1f}%")
        table.add_row("Sharpe Ratio", f"{state.get('sharpe_ratio', 0):.2f}")

        self.console.print(table)

    def show_trading_controls(self):
        """Display trading controls menu"""
        self._print("\n[bold]Trading Controls[/bold]")

        while True:
            state = self.system_state
            self._print(f"\nCurrent Status: {'[green]Running[/green]' if state['running'] else '[red]Stopped[/red]'}")
            self._print(f"Mode: {state['mode'].upper()}")

            self._print("\n1. Start trading")
            self._print("2. Stop trading")
            self._print("3. Switch mode (paper/live)")
            self._print("4. View recent trades")
            self._print("0. Back to main menu")

            choice = self._input("\nSelect option")

            if choice == '0':
                break
            elif choice == '1':
                self._start_trading()
            elif choice == '2':
                self._stop_trading()
            elif choice == '3':
                self._switch_mode()
            elif choice == '4':
                self._show_recent_trades()

    def _start_trading(self):
        """Start the trading bot"""
        if self.state_manager:
            self.state_manager.update_trading_state(running=True)
            self._print("[green]✓[/green] Trading started")
        else:
            self._print("[yellow]State manager not available - cannot control trading[/yellow]")

    def _stop_trading(self):
        """Stop the trading bot"""
        if self.state_manager:
            self.state_manager.update_trading_state(running=False)
            self._print("[green]✓[/green] Trading stopped")
        else:
            self._print("[yellow]State manager not available - cannot control trading[/yellow]")

    def _switch_mode(self):
        """Switch between paper and live mode"""
        if not self._confirm("[yellow]Switch trading mode? This will affect real funds in live mode![/yellow]"):
            return

        state = self.system_state
        new_mode = 'live' if state['mode'] == 'paper' else 'paper'

        if new_mode == 'live':
            confirm = self._input("Type 'LIVE' to confirm switching to live mode")
            if confirm != 'LIVE':
                self._print("Mode switch cancelled")
                return

        if self.state_manager:
            self.state_manager.update_trading_state(mode=new_mode)
            self._print(f"[green]✓[/green] Switched to {new_mode.upper()} mode")
        else:
            self._print("[yellow]State manager not available[/yellow]")

    def _show_recent_trades(self):
        """Show recent trades"""
        if self.state_manager:
            trades = self.state_manager.get_recent_trades(limit=10)
            if not trades:
                self._print("[dim]No recent trades[/dim]")
                return

            if self.console:
                table = Table(title="Recent Trades")
                table.add_column("Time")
                table.add_column("Symbol")
                table.add_column("Side")
                table.add_column("Profit")
                table.add_column("Status")

                for trade in trades:
                    profit = trade.get('net_profit', 0)
                    profit_style = 'green' if profit > 0 else 'red' if profit < 0 else 'dim'
                    table.add_row(
                        trade.get('recorded_at', 'N/A')[:19],
                        trade.get('symbol', 'N/A'),
                        trade.get('side', 'N/A'),
                        f"[{profit_style}]${profit:.2f}[/{profit_style}]",
                        trade.get('status', 'N/A')
                    )
                self.console.print(table)
            else:
                for trade in trades:
                    print(f"  {trade.get('recorded_at', '')[:19]} | {trade.get('symbol', '')} | ${trade.get('net_profit', 0):.2f}")
        else:
            self._print("[dim]No trade data available[/dim]")

    def show_portfolio_risk(self):
        """Display portfolio and risk metrics"""
        self._print("\n[bold]Portfolio & Risk[/bold]")

        state = self.system_state

        if self.console:
            table = Table(title="Portfolio Overview")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Current Capital", f"${state['current_capital']:.2f}")
            table.add_row("Total Profit", f"${state['total_profit']:.2f}")
            table.add_row("Win Rate", f"{state.get('win_rate', 0)*100:.1f}%")
            table.add_row("Sharpe Ratio", f"{state.get('sharpe_ratio', 0):.2f}")

            self.console.print(table)

            # Risk metrics if available from state manager
            if self.state_manager:
                signal_state = self.state_manager.get_signal_state()

                risk_table = Table(title="Market Sentiment")
                risk_table.add_column("Asset", style="cyan")
                risk_table.add_column("Sentiment")
                risk_table.add_column("Score")

                sentiment_score = signal_state.market_sentiment
                sentiment_level = 'fear' if sentiment_score < 40 else 'greed' if sentiment_score > 60 else 'neutral'
                color = 'red' if sentiment_level == 'fear' else 'green' if sentiment_level == 'greed' else 'yellow'
                risk_table.add_row("Market", f"[{color}]{sentiment_level.upper()}[/{color}]", f"{sentiment_score:.0f}")

                for asset, score in signal_state.asset_sentiment.items():
                    level = 'fear' if score < 40 else 'greed' if score > 60 else 'neutral'
                    c = 'red' if level == 'fear' else 'green' if level == 'greed' else 'yellow'
                    risk_table.add_row(asset.upper(), f"[{c}]{level.upper()}[/{c}]", f"{score:.0f}")

                self.console.print(risk_table)
        else:
            print(f"\nPortfolio:")
            print(f"  Capital: ${state['current_capital']:.2f}")
            print(f"  Profit: ${state['total_profit']:.2f}")
            print(f"  Win Rate: {state.get('win_rate', 0)*100:.1f}%")

    def show_configuration(self):
        """Display configuration menu"""
        self._print("\n[bold]Configuration[/bold]")
        self._print("\nCurrent configuration can be modified in config/config.yaml")

        if self.console:
            try:
                import yaml
                from pathlib import Path
                config_path = Path("config/config.yaml")
                if config_path.exists():
                    with open(config_path) as f:
                        config = yaml.safe_load(f)

                    table = Table(title="Trading Configuration")
                    table.add_column("Setting", style="cyan")
                    table.add_column("Value", style="green")

                    trading = config.get('trading', {})
                    table.add_row("Mode", trading.get('mode', 'paper'))
                    table.add_row("Min Spread %", str(trading.get('min_spread_percent', 0.3)))
                    table.add_row("Max Position USD", str(trading.get('max_position_usd', 500)))
                    table.add_row("Max Daily Loss USD", str(trading.get('max_daily_loss_usd', 100)))
                    table.add_row("Max Daily Trades", str(trading.get('max_daily_trades', 20)))

                    self.console.print(table)
                else:
                    self._print("[yellow]Configuration file not found[/yellow]")
            except Exception as e:
                self._print(f"[red]Error reading config: {e}[/red]")
        else:
            print("Edit config/config.yaml to modify settings")

    def show_audit_logs(self):
        """Display audit log viewer"""
        self._print("\n[bold]Audit Logs[/bold]")

        limit = 20
        try:
            limit_input = self._input("Number of entries to show (default 20)")
            if limit_input:
                limit = int(limit_input)
        except ValueError:
            pass

        events = self.audit_logger.query(limit=limit)

        if not events:
            self._print("[dim]No audit events found[/dim]")
            return

        if self.console:
            table = Table(title=f"Last {len(events)} Audit Events")
            table.add_column("Time", style="dim")
            table.add_column("Category")
            table.add_column("Action")
            table.add_column("Actor")
            table.add_column("Status")

            for event in events:
                status_icon = "[green]✓[/green]" if event.success else "[red]✗[/red]"
                table.add_row(
                    event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    event.category.value if hasattr(event.category, 'value') else str(event.category),
                    event.action,
                    event.actor,
                    status_icon
                )

            self.console.print(table)
        else:
            for event in events:
                status = "✓" if event.success else "✗"
                print(f"  {event.timestamp.strftime('%H:%M:%S')} [{event.category}] {status} {event.action} by {event.actor}")

    def show_user_management(self):
        """Display user management menu"""
        self._print("\n[bold]User Management[/bold]")

        while True:
            self._print("\n1. List users")
            self._print("2. Add user")
            self._print("3. Change user role")
            self._print("4. Reset user password")
            self._print("0. Back to main menu")

            choice = self._input("\nSelect option")

            if choice == '0':
                break
            elif choice == '1':
                self._list_users()
            elif choice == '2':
                self._add_user()
            elif choice == '3':
                self._change_user_role()
            elif choice == '4':
                self._reset_user_password()

    def _list_users(self):
        """List all users"""
        if self.console:
            table = Table(title="Users")
            table.add_column("Username", style="cyan")
            table.add_column("Role")
            table.add_column("2FA")
            table.add_column("Created")

            for user in self.auth_manager._users.values():
                mfa = "[green]Enabled[/green]" if user.totp_enabled else "[dim]Disabled[/dim]"
                created = user.created_at.strftime('%Y-%m-%d') if user.created_at else "N/A"
                table.add_row(user.username, user.role, mfa, created)

            self.console.print(table)
        else:
            for user in self.auth_manager._users.values():
                mfa = "2FA" if user.totp_enabled else ""
                print(f"  {user.username} ({user.role}) {mfa}")

    def _add_user(self):
        """Add a new user"""
        username = self._input("Username")
        role = self._input("Role (viewer/analyst/trader/admin)")
        if role not in ['viewer', 'analyst', 'trader', 'admin']:
            self._print("[red]Invalid role[/red]")
            return

        password = self._password("Password (min 12 chars)")
        if len(password) < 12:
            self._print("[red]Password too short[/red]")
            return

        try:
            self.auth_manager.create_user(username, password, role=role)
            self._print(f"[green]✓[/green] User '{username}' created with role '{role}'")

            self.audit_logger.log_security_event(
                action='user_created',
                actor=self.session.username,
                resource=username,
                details={'role': role}
            )
        except Exception as e:
            self._print(f"[red]Error: {e}[/red]")

    def _change_user_role(self):
        """Change a user's role"""
        username = self._input("Username")
        user = self.auth_manager.get_user(username)
        if not user:
            self._print("[red]User not found[/red]")
            return

        self._print(f"Current role: {user.role}")
        new_role = self._input("New role (viewer/analyst/trader/admin)")

        if new_role in ['viewer', 'analyst', 'trader', 'admin']:
            user.role = new_role
            self._print(f"[green]✓[/green] Role changed to '{new_role}'")
        else:
            self._print("[red]Invalid role[/red]")

    def _reset_user_password(self):
        """Reset a user's password"""
        username = self._input("Username")
        user = self.auth_manager.get_user(username)
        if not user:
            self._print("[red]User not found[/red]")
            return

        new_password = self._password("New password (min 12 chars)")
        if len(new_password) < 12:
            self._print("[red]Password too short[/red]")
            return

        # Hash and update password
        import hashlib
        user.password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self._print(f"[green]✓[/green] Password reset for '{username}'")

    def show_credentials_menu(self):
        """Manage API credentials"""
        self._print("\n[bold]Credential Management[/bold]")

        while True:
            self._print("\n1. List configured exchanges")
            self._print("2. Add exchange credentials")
            self._print("3. Update exchange credentials")
            self._print("4. Remove exchange credentials")
            self._print("0. Back to main menu")

            choice = self._input("\nSelect option")

            if choice == '0':
                break
            elif choice == '1':
                self._list_credentials()
            elif choice == '2':
                self._add_credentials()
            elif choice == '3':
                self._update_credentials()
            elif choice == '4':
                self._remove_credentials()

    def _list_credentials(self):
        """List configured credential (metadata only)"""
        secrets = self.secrets_manager.list_secrets()
        exchanges = set()

        for secret in secrets:
            if secret.endswith('_api_key'):
                exchange = secret.replace('_api_key', '')
                exchanges.add(exchange)

        if not exchanges:
            self._print("[yellow]No exchange credentials configured[/yellow]")
            return

        if self.console:
            table = Table(title="Configured Exchanges")
            table.add_column("Exchange", style="cyan")
            table.add_column("API Key", style="green")
            table.add_column("Secret", style="green")
            table.add_column("Passphrase", style="green")

            for exchange in sorted(exchanges):
                has_key = f"{exchange}_api_key" in secrets
                has_secret = f"{exchange}_secret" in secrets
                has_pass = f"{exchange}_passphrase" in secrets

                table.add_row(
                    exchange,
                    "✓" if has_key else "✗",
                    "✓" if has_secret else "✗",
                    "✓" if has_pass else "-"
                )

            self.console.print(table)
        else:
            print("\nConfigured exchanges:")
            for exchange in sorted(exchanges):
                print(f"  - {exchange}")

    def _add_credentials(self):
        """Add new exchange credentials"""
        exchanges = ['binance', 'coinbase', 'kraken', 'bybit', 'okx', 'kucoin']

        self._print("\nAvailable exchanges: " + ", ".join(exchanges))
        exchange = self._input("Exchange name").lower()

        if exchange not in exchanges:
            self._print(f"[red]Unknown exchange: {exchange}[/red]")
            return

        api_key = self._password("API Key")
        secret = self._password("Secret Key")

        # Some exchanges need passphrase
        needs_passphrase = exchange in ['coinbase', 'kucoin', 'okx']
        passphrase = None
        if needs_passphrase:
            passphrase = self._password("Passphrase")

        # Confirm
        if not self._confirm(f"Save credentials for {exchange}?"):
            return

        # Save encrypted
        self.secrets_manager.set_secret(f"{exchange}_api_key", api_key)
        self.secrets_manager.set_secret(f"{exchange}_secret", secret)
        if passphrase:
            self.secrets_manager.set_secret(f"{exchange}_passphrase", passphrase)

        self.audit_logger.log_security_event(
            action='credentials_added',
            actor=self.session.username,
            resource=exchange,
            details={'exchange': exchange}
        )

        self._print(f"[green]✓[/green] Credentials for {exchange} saved securely")

    def _update_credentials(self):
        """Update existing credentials"""
        secrets = self.secrets_manager.list_secrets()
        exchanges = set()

        for secret in secrets:
            if secret.endswith('_api_key'):
                exchanges.add(secret.replace('_api_key', ''))

        if not exchanges:
            self._print("[yellow]No credentials to update[/yellow]")
            return

        self._print("Configured: " + ", ".join(exchanges))
        exchange = self._input("Exchange to update").lower()

        if exchange not in exchanges:
            self._print(f"[red]{exchange} not configured[/red]")
            return

        self._print("\nEnter new values (press Enter to keep existing):")

        api_key = self._password("New API Key (Enter to skip)") or None
        secret = self._password("New Secret Key (Enter to skip)") or None

        if api_key:
            self.secrets_manager.set_secret(f"{exchange}_api_key", api_key)
        if secret:
            self.secrets_manager.set_secret(f"{exchange}_secret", secret)

        self.audit_logger.log_security_event(
            action='credentials_updated',
            actor=self.session.username,
            resource=exchange,
            details={'exchange': exchange}
        )

        self._print(f"[green]✓[/green] Credentials updated")

    def _remove_credentials(self):
        """Remove exchange credentials"""
        secrets = self.secrets_manager.list_secrets()
        exchanges = set()

        for secret in secrets:
            if secret.endswith('_api_key'):
                exchanges.add(secret.replace('_api_key', ''))

        if not exchanges:
            self._print("[yellow]No credentials to remove[/yellow]")
            return

        self._print("Configured: " + ", ".join(exchanges))
        exchange = self._input("Exchange to remove").lower()

        if exchange not in exchanges:
            self._print(f"[red]{exchange} not configured[/red]")
            return

        if not self._confirm(f"[red]Remove credentials for {exchange}?[/red]"):
            return

        self.secrets_manager.delete_secret(f"{exchange}_api_key")
        self.secrets_manager.delete_secret(f"{exchange}_secret")
        self.secrets_manager.delete_secret(f"{exchange}_passphrase")

        self.audit_logger.log_security_event(
            action='credentials_removed',
            actor=self.session.username,
            resource=exchange,
            details={'exchange': exchange}
        )

        self._print(f"[green]✓[/green] Credentials for {exchange} removed")

    def show_emergency_controls(self):
        """Emergency control panel"""
        self._print("\n[bold red]⚠ Emergency Controls[/bold red]")
        self._print("[dim]Use these controls to immediately halt trading operations[/dim]\n")

        status = self.emergency_controls.get_emergency_status()

        if status['is_active']:
            self._print("[red]Emergency stop is ACTIVE[/red]")
            self._print(f"Reason: {status['reason']}")
            self._print(f"Activated by: {status['activated_by']}")

            if self._confirm("\n[yellow]Deactivate emergency stop?[/yellow]"):
                totp = self._input("Enter 2FA code to confirm")
                user = self.auth_manager.get_user(self.session.username)

                if user and user.totp_enabled:
                    from security.auth import TOTP
                    if not TOTP.verify(user.totp_secret, totp):
                        self._print("[red]Invalid 2FA code[/red]")
                        return

                if self.emergency_controls.deactivate_emergency_stop(
                    self.session.username,
                    self.session.role,
                    'localhost'
                ):
                    self.audit_logger.log_security_event(
                        action='emergency_stop_deactivated',
                        actor=self.session.username,
                        resource='trading_system',
                        details={}
                    )
                    self._print("[green]Emergency stop deactivated[/green]")
        else:
            self._print("[green]System operating normally[/green]")

            if self._confirm("\n[red]ACTIVATE EMERGENCY STOP?[/red]"):
                reason = self._input("Reason for emergency stop")
                totp = self._input("Enter 2FA code to confirm")

                user = self.auth_manager.get_user(self.session.username)
                if user and user.totp_enabled:
                    from security.auth import TOTP
                    if not TOTP.verify(user.totp_secret, totp):
                        self._print("[red]Invalid 2FA code[/red]")
                        return

                if self.emergency_controls.activate_emergency_stop(
                    self.session.username,
                    self.session.role,
                    reason,
                    'localhost'
                ):
                    self.audit_logger.log_security_event(
                        action='emergency_stop_activated',
                        actor=self.session.username,
                        resource='trading_system',
                        details={'reason': reason}
                    )
                    self._print("[red]EMERGENCY STOP ACTIVATED[/red]")

    async def run(self):
        """Main dashboard loop"""
        if not await self.initialize():
            return

        if not await self.login():
            return

        while True:
            try:
                menu = self.show_main_menu()
                choice = self._input("\nSelect option")

                if choice == '0':
                    self.audit_logger.log_logout(
                        self.session.username,
                        'localhost'
                    )
                    self._print("\n[dim]Goodbye![/dim]\n")
                    break
                elif choice == '1':
                    self.show_system_status()
                elif choice == '2':
                    self.show_trading_controls()
                elif choice == '3':
                    self.show_portfolio_risk()
                elif choice == '4':
                    self.show_configuration()
                elif choice == '5':
                    self.show_credentials_menu()
                elif choice == '6':
                    self.show_audit_logs()
                elif choice == '7':
                    self.show_user_management()
                elif choice == '8':
                    self.show_emergency_controls()
                else:
                    self._print(f"[yellow]Unknown option: {choice}[/yellow]")

            except KeyboardInterrupt:
                self._print("\n\n[dim]Use option 0 to logout properly[/dim]")

        # Cleanup
        if self.audit_logger:
            self.audit_logger.shutdown()


async def run_dashboard():
    """Entry point for dashboard"""
    dashboard = Dashboard()
    await dashboard.run()


if __name__ == "__main__":
    asyncio.run(run_dashboard())
