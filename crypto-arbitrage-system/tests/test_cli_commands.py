"""
Tests for CLI command handler.

Tests verify:
- Argument parsing for all subcommands
- Command routing to correct handlers
- Live trading confirmation safeguard
- Help text display
- Sync main() entry point wraps async correctly
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from io import StringIO

from src.cli.commands import CommandHandler, main


class TestArgumentParsing:
    """Test argparse subcommand parsing"""

    @pytest.fixture
    def handler(self):
        return CommandHandler()

    def test_start_default_mode(self, handler):
        parsed = handler.parser.parse_args(["start"])
        assert parsed.command == "start"
        assert parsed.mode == "paper"
        assert parsed.config == "config/config.yaml"

    def test_start_live_mode(self, handler):
        parsed = handler.parser.parse_args(["start", "--mode", "live"])
        assert parsed.mode == "live"

    def test_start_custom_config(self, handler):
        parsed = handler.parser.parse_args(["start", "--config", "/etc/carbs.yaml"])
        assert parsed.config == "/etc/carbs.yaml"

    def test_stop_command(self, handler):
        parsed = handler.parser.parse_args(["stop"])
        assert parsed.command == "stop"

    def test_status_command(self, handler):
        parsed = handler.parser.parse_args(["status"])
        assert parsed.command == "status"

    def test_setup_command(self, handler):
        parsed = handler.parser.parse_args(["setup"])
        assert parsed.command == "setup"
        assert parsed.force is False

    def test_setup_force(self, handler):
        parsed = handler.parser.parse_args(["setup", "--force"])
        assert parsed.force is True

    def test_creds_add(self, handler):
        parsed = handler.parser.parse_args(["creds", "add", "binance"])
        assert parsed.command == "creds"
        assert parsed.creds_action == "add"
        assert parsed.exchange == "binance"

    def test_creds_list(self, handler):
        parsed = handler.parser.parse_args(["creds", "list"])
        assert parsed.creds_action == "list"

    def test_creds_remove(self, handler):
        parsed = handler.parser.parse_args(["creds", "remove", "coinbase"])
        assert parsed.creds_action == "remove"
        assert parsed.exchange == "coinbase"

    def test_audit_defaults(self, handler):
        parsed = handler.parser.parse_args(["audit"])
        assert parsed.command == "audit"
        assert parsed.limit == 20
        assert parsed.category is None

    def test_audit_with_options(self, handler):
        parsed = handler.parser.parse_args(["audit", "--limit", "50", "--category", "trade"])
        assert parsed.limit == 50
        assert parsed.category == "trade"

    def test_emergency_stop(self, handler):
        parsed = handler.parser.parse_args(["emergency", "stop", "--reason", "API issue"])
        assert parsed.command == "emergency"
        assert parsed.action == "stop"
        assert parsed.reason == "API issue"

    def test_balance_command(self, handler):
        parsed = handler.parser.parse_args(["balance", "--exchange", "binance", "--currency", "BTC"])
        assert parsed.command == "balance"
        assert parsed.exchange == "binance"
        assert parsed.currency == "BTC"

    def test_trades_command(self, handler):
        parsed = handler.parser.parse_args(["trades", "--limit", "50", "--symbol", "BTCUSDT"])
        assert parsed.command == "trades"
        assert parsed.limit == 50
        assert parsed.symbol == "BTCUSDT"

    def test_health_verbose(self, handler):
        parsed = handler.parser.parse_args(["health", "-v"])
        assert parsed.command == "health"
        assert parsed.verbose is True

    def test_config_show(self, handler):
        parsed = handler.parser.parse_args(["config", "show"])
        assert parsed.command == "config"
        assert parsed.config_action == "show"

    def test_config_set(self, handler):
        parsed = handler.parser.parse_args(["config", "set", "trading.mode", "live"])
        assert parsed.config_action == "set"
        assert parsed.key == "trading.mode"
        assert parsed.value == "live"

    def test_opportunities_command(self, handler):
        parsed = handler.parser.parse_args(["opportunities", "--min-spread", "5.0", "--symbol", "BTCUSDT"])
        assert parsed.min_spread == 5.0
        assert parsed.symbol == "BTCUSDT"

    def test_metrics_period(self, handler):
        parsed = handler.parser.parse_args(["metrics", "--period", "7d"])
        assert parsed.period == "7d"

    def test_backtest_command(self, handler):
        parsed = handler.parser.parse_args(["backtest", "--start", "2024-01-01", "--end", "2024-06-01"])
        assert parsed.command == "backtest"
        assert parsed.start == "2024-01-01"
        assert parsed.end == "2024-06-01"
        assert parsed.symbol == "BTCUSDT"  # default

    def test_user_add(self, handler):
        parsed = handler.parser.parse_args(["user", "add", "testuser", "--role", "trader"])
        assert parsed.command == "user"
        assert parsed.user_action == "add"
        assert parsed.username == "testuser"
        assert parsed.role == "trader"


class TestCommandRouting:
    """Test that commands route to correct handlers"""

    @pytest.fixture
    def handler(self):
        h = CommandHandler()
        # Mock all handlers
        h._handle_setup = AsyncMock()
        h._handle_dashboard = AsyncMock()
        h._handle_start = AsyncMock()
        h._handle_stop = AsyncMock()
        h._handle_status = AsyncMock()
        h._handle_creds = AsyncMock()
        h._handle_audit = AsyncMock()
        h._handle_user = AsyncMock()
        h._handle_emergency = AsyncMock()
        h._handle_balance = AsyncMock()
        h._handle_trades = AsyncMock()
        h._handle_positions = AsyncMock()
        h._handle_health = AsyncMock()
        h._handle_config = AsyncMock()
        h._handle_opportunities = AsyncMock()
        h._handle_metrics = AsyncMock()
        h._handle_backtest = AsyncMock()
        return h

    async def test_routes_start(self, handler):
        await handler.handle(["start"])
        handler._handle_start.assert_called_once()

    async def test_routes_stop(self, handler):
        await handler.handle(["stop"])
        handler._handle_stop.assert_called_once()

    async def test_routes_status(self, handler):
        await handler.handle(["status"])
        handler._handle_status.assert_called_once()

    async def test_routes_health(self, handler):
        await handler.handle(["health"])
        handler._handle_health.assert_called_once()

    async def test_routes_emergency(self, handler):
        await handler.handle(["emergency", "status"])
        handler._handle_emergency.assert_called_once()

    async def test_no_command_shows_help(self, handler, capsys):
        await handler.handle([])
        # No handler should have been called
        handler._handle_start.assert_not_called()


class TestLiveTradingSafeguard:
    """Test that live trading requires explicit confirmation"""

    async def test_live_mode_requires_confirmation(self, capsys):
        handler = CommandHandler()
        with patch("builtins.input", return_value="NOPE"):
            await handler._handle_start(
                handler.parser.parse_args(["start", "--mode", "live"])
            )
        output = capsys.readouterr().out
        assert "Aborted" in output

    async def test_live_mode_proceeds_with_confirm(self, capsys):
        handler = CommandHandler()
        with patch("builtins.input", return_value="CONFIRM"):
            await handler._handle_start(
                handler.parser.parse_args(["start", "--mode", "live"])
            )
        output = capsys.readouterr().out
        assert "Aborted" not in output

    async def test_paper_mode_no_confirmation(self, capsys):
        handler = CommandHandler()
        await handler._handle_start(
            handler.parser.parse_args(["start", "--mode", "paper"])
        )
        output = capsys.readouterr().out
        assert "CONFIRM" not in output


class TestSyncEntryPoint:
    """Test that main() is a sync function usable as console_scripts entry"""

    def test_main_is_sync(self):
        """main() should be a regular function, not async"""
        assert not asyncio.iscoroutinefunction(main)

    def test_main_calls_async_handler(self):
        with patch("src.cli.commands.asyncio") as mock_asyncio:
            with patch("src.cli.commands.CommandHandler") as MockHandler:
                mock_handler = MagicMock()
                mock_handler.handle = AsyncMock()
                MockHandler.return_value = mock_handler
                main()
                mock_asyncio.run.assert_called_once()
