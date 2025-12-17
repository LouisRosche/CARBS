"""
Web Routes

FastAPI route handlers for dashboard pages and API.
"""

import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .templates import render_page
from .data import get_dashboard_data, DEFAULT_DATA

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def render_sentiment_widget(sentiment_data: Dict = None) -> str:
    """Render sentiment display widget"""
    if sentiment_data is None:
        sentiment_data = get_dashboard_data().get('sentiment', DEFAULT_DATA['sentiment'])

    html = ""
    for asset, data in sentiment_data.items():
        if isinstance(data, dict):
            score = data.get('score', 50)
            level = data.get('level', 'neutral')
            level_class = "fear" if score < 40 else "greed" if score > 60 else "neutral"
            html += f"""
                <div class="metric">
                    <div class="metric-label">{asset.upper()}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="metric-value neutral" style="font-size: 1.25rem;">{score}</span>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">{level}</span>
                    </div>
                    <div class="sentiment-bar">
                        <div class="sentiment-fill {level_class}" style="width: {score}%;"></div>
                    </div>
                </div>
            """
    return html if html else "<div class='empty-state'>No sentiment data available</div>"


def render_signals_widget(signals_data: list = None) -> str:
    """Render active signals widget"""
    if signals_data is None:
        signals_data = get_dashboard_data().get('signals', [])

    if not signals_data:
        return """
            <div class="empty-state">
                <p>No active signals</p>
                <p style="font-size: 0.75rem; margin-top: 5px;">Signals will appear when opportunities are detected</p>
            </div>
        """

    html = ""
    for signal in signals_data:
        signal_type = signal.get('type', signal.get('signal', 'unknown')).lower()
        signal_class = "signal-buy" if "buy" in signal_type else "signal-sell"
        type_class = "buy" if "buy" in signal_type else "sell"
        asset = signal.get('asset', signal.get('symbol', 'UNKNOWN'))
        confidence = signal.get('confidence', 0.5)

        html += f"""
            <div class="signal-item {signal_class}">
                <div>
                    <span class="signal-asset">{asset}</span>
                    <span class="signal-type {type_class}">{signal_type.upper()}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">Confidence</div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: {confidence * 100}%;"></div>
                    </div>
                </div>
            </div>
        """
    return html


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page"""
    data = get_dashboard_data()
    portfolio = data.get('portfolio', DEFAULT_DATA['portfolio'])
    system = data.get('system', DEFAULT_DATA['system'])
    status = data.get('status', 'paper')

    pnl_class = 'positive' if portfolio.get('daily_pnl', 0) >= 0 else 'negative'
    exchanges_count = len(system.get('exchanges_connected', []))

    content = f"""
        <header>
            <div class="logo">CARBS</div>
            <div>
                <span class="live-dot"></span>
                <span class="status-badge status-{status}">{status.upper()}</span>
                {"<span style='color: var(--accent-red); margin-left: 10px;'>EMERGENCY STOP</span>" if system.get('emergency_stop') else ""}
            </div>
        </header>

        <nav class="nav">
            <a href="/" class="nav-link active">Dashboard</a>
            <a href="/signals" class="nav-link">Signals</a>
            <a href="/trades" class="nav-link">Trades</a>
            <a href="/settings" class="nav-link">Settings</a>
        </nav>

        <div class="grid">
            <!-- Portfolio Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Portfolio</span>
                    <span class="refresh-indicator"
                          hx-get="/api/portfolio"
                          hx-trigger="every 30s"
                          hx-swap="outerHTML">
                    </span>
                </div>
                <div id="portfolio-content"
                     hx-get="/api/portfolio"
                     hx-trigger="load, every 30s"
                     hx-swap="innerHTML">
                    <div class="metric">
                        <div class="metric-label">Total Value</div>
                        <div class="metric-value neutral">${portfolio.get('total_value', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Today's P&L</div>
                        <div class="metric-value {pnl_class}">
                            ${portfolio.get('daily_pnl', 0):+.2f} ({portfolio.get('daily_pnl_pct', 0):+.2f}%)
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Open Positions</div>
                        <div class="metric-value neutral">{portfolio.get('open_positions', 0)}</div>
                    </div>
                </div>
            </div>

            <!-- Market Sentiment Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Market Sentiment</span>
                </div>
                <div id="sentiment-content"
                     hx-get="/api/sentiment"
                     hx-trigger="load, every 60s"
                     hx-swap="innerHTML">
                    {render_sentiment_widget(data.get('sentiment', DEFAULT_DATA['sentiment']))}
                </div>
            </div>

            <!-- Active Signals Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Active Signals</span>
                </div>
                <div id="signals-content"
                     hx-get="/api/signals"
                     hx-trigger="load, every 30s"
                     hx-swap="innerHTML">
                    {render_signals_widget(data.get('signals', []))}
                </div>
            </div>

            <!-- System Status Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">System Status</span>
                </div>
                <div id="status-content"
                     hx-get="/api/status"
                     hx-trigger="load, every 10s"
                     hx-swap="innerHTML">
                    <div class="metric">
                        <div class="metric-label">Mode</div>
                        <div class="metric-value neutral">{system.get('mode', 'paper').upper()}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Running</div>
                        <div class="metric-value {'positive' if system.get('running') else 'negative'}">
                            {'YES' if system.get('running') else 'NO'}
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Exchanges Connected</div>
                        <div class="metric-value neutral">{exchanges_count}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Opportunities (Detected/Executed)</div>
                        <div class="metric-value neutral">{system.get('opportunities_detected', 0)} / {system.get('opportunities_executed', 0)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Win Rate / Sharpe</div>
                        <div class="metric-value neutral">{system.get('win_rate', 0)*100:.1f}% / {system.get('sharpe_ratio', 0):.2f}</div>
                    </div>
                </div>
            </div>
        </div>

        <footer>
            CARBS v1.0 | <span id="clock">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</span>
        </footer>
    """
    return HTMLResponse(render_page(content))


@router.get("/api/portfolio", response_class=HTMLResponse)
async def get_portfolio():
    """API endpoint for portfolio data (HTMX partial)"""
    data = get_dashboard_data()
    portfolio = data.get('portfolio', DEFAULT_DATA['portfolio'])
    pnl_class = 'positive' if portfolio.get('daily_pnl', 0) >= 0 else 'negative'

    return HTMLResponse(f"""
        <div class="metric">
            <div class="metric-label">Total Value</div>
            <div class="metric-value neutral">${portfolio.get('total_value', 0):.2f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Today's P&L</div>
            <div class="metric-value {pnl_class}">
                ${portfolio.get('daily_pnl', 0):+.2f} ({portfolio.get('daily_pnl_pct', 0):+.2f}%)
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Open Positions</div>
            <div class="metric-value neutral">{portfolio.get('open_positions', 0)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Total Profit</div>
            <div class="metric-value {'positive' if portfolio.get('total_profit', 0) >= 0 else 'negative'}">
                ${portfolio.get('total_profit', 0):+.2f}
            </div>
        </div>
    """)


@router.get("/api/sentiment", response_class=HTMLResponse)
async def get_sentiment():
    """API endpoint for sentiment data (HTMX partial)"""
    data = get_dashboard_data()
    return HTMLResponse(render_sentiment_widget(data.get('sentiment')))


@router.get("/api/signals", response_class=HTMLResponse)
async def get_signals():
    """API endpoint for signals (HTMX partial)"""
    data = get_dashboard_data()
    return HTMLResponse(render_signals_widget(data.get('signals')))


@router.get("/api/status", response_class=HTMLResponse)
async def get_status():
    """API endpoint for system status (HTMX partial)"""
    data = get_dashboard_data()
    system = data.get('system', DEFAULT_DATA['system'])
    exchanges_count = len(system.get('exchanges_connected', []))

    return HTMLResponse(f"""
        <div class="metric">
            <div class="metric-label">Mode</div>
            <div class="metric-value neutral">{system.get('mode', 'paper').upper()}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Running</div>
            <div class="metric-value {'positive' if system.get('running') else 'negative'}">
                {'YES' if system.get('running') else 'NO'}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Exchanges Connected</div>
            <div class="metric-value neutral">{exchanges_count}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Opportunities (Detected/Executed)</div>
            <div class="metric-value neutral">{system.get('opportunities_detected', 0)} / {system.get('opportunities_executed', 0)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Win Rate / Sharpe</div>
            <div class="metric-value neutral">{system.get('win_rate', 0)*100:.1f}% / {system.get('sharpe_ratio', 0):.2f}</div>
        </div>
    """)


@router.get("/signals", response_class=HTMLResponse)
async def signals_page():
    """Signals page"""
    content = """
        <header>
            <div class="logo">CARBS</div>
            <div>
                <span class="live-dot"></span>
                <span class="status-badge status-paper">PAPER</span>
            </div>
        </header>

        <nav class="nav">
            <a href="/" class="nav-link">Dashboard</a>
            <a href="/signals" class="nav-link active">Signals</a>
            <a href="/trades" class="nav-link">Trades</a>
            <a href="/settings" class="nav-link">Settings</a>
        </nav>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Signal History</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Asset</th>
                        <th>Signal</th>
                        <th>Confidence</th>
                        <th>Reasons</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 40px;">
                            No signals yet. Signals will appear when the system detects opportunities.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <footer>
            CARBS v1.0
        </footer>
    """
    return HTMLResponse(render_page(content, "Signals"))


@router.get("/trades", response_class=HTMLResponse)
async def trades_page():
    """Trades page"""
    content = """
        <header>
            <div class="logo">CARBS</div>
            <div>
                <span class="live-dot"></span>
                <span class="status-badge status-paper">PAPER</span>
            </div>
        </header>

        <nav class="nav">
            <a href="/" class="nav-link">Dashboard</a>
            <a href="/signals" class="nav-link">Signals</a>
            <a href="/trades" class="nav-link active">Trades</a>
            <a href="/settings" class="nav-link">Settings</a>
        </nav>

        <div class="card">
            <div class="card-header">
                <span class="card-title">Trade History</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Asset</th>
                        <th>Side</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 40px;">
                            No trades yet. Start paper trading to see trade history.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <footer>
            CARBS v1.0
        </footer>
    """
    return HTMLResponse(render_page(content, "Trades"))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Settings page"""
    content = """
        <header>
            <div class="logo">CARBS</div>
            <div>
                <span class="status-badge status-paper">PAPER</span>
            </div>
        </header>

        <nav class="nav">
            <a href="/" class="nav-link">Dashboard</a>
            <a href="/signals" class="nav-link">Signals</a>
            <a href="/trades" class="nav-link">Trades</a>
            <a href="/settings" class="nav-link active">Settings</a>
        </nav>

        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Trading Mode</span>
                </div>
                <div class="metric">
                    <div class="metric-label">Current Mode</div>
                    <div class="metric-value neutral">PAPER</div>
                </div>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 10px;">
                    Paper trading mode is active. Trades are simulated without real funds.
                </p>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Exchanges</span>
                </div>
                <p style="color: var(--text-secondary); font-size: 0.875rem;">
                    No exchanges connected. Use the CLI to add exchange credentials:
                </p>
                <pre style="background: var(--bg-tertiary); padding: 10px; border-radius: 4px; margin-top: 10px; font-size: 0.75rem; overflow-x: auto;">
python -m src.cli.commands creds add binance</pre>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Strategy Parameters</span>
                </div>
                <div class="metric">
                    <div class="metric-label">Min Confidence</div>
                    <div class="metric-value neutral" style="font-size: 1.25rem;">60%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Max Position Size</div>
                    <div class="metric-value neutral" style="font-size: 1.25rem;">25%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Default Stop Loss</div>
                    <div class="metric-value neutral" style="font-size: 1.25rem;">3%</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Notifications</span>
                </div>
                <div class="metric">
                    <div class="metric-label">Telegram</div>
                    <div class="metric-value negative" style="font-size: 1rem;">Not Connected</div>
                </div>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 10px;">
                    Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
                </p>
            </div>
        </div>

        <footer>
            CARBS v1.0
        </footer>
    """
    return HTMLResponse(render_page(content, "Settings"))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }
