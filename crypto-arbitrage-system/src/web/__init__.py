"""
Web Dashboard

Lightweight web interface using FastAPI + HTMX.
No JavaScript frameworks - just HTML that works.

Features:
- Real-time sentiment display
- Active signals view
- Portfolio status
- Trade history
- System health
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CARBS Dashboard",
    description="Crypto Arbitrage System Dashboard",
    version="1.0.0"
)

# HTML Templates (inline for simplicity)
BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CARBS Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-yellow: #d29922;
            --accent-blue: #58a6ff;
            --border-color: #30363d;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--accent-blue);
        }

        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .status-live { background: var(--accent-green); color: #000; }
        .status-paper { background: var(--accent-yellow); color: #000; }
        .status-offline { background: var(--accent-red); color: #fff; }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }

        .card-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .metric {
            margin-bottom: 15px;
        }

        .metric-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }

        .metric-value {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .metric-value.positive { color: var(--accent-green); }
        .metric-value.negative { color: var(--accent-red); }
        .metric-value.neutral { color: var(--text-primary); }

        .sentiment-bar {
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }

        .sentiment-fill {
            height: 100%;
            transition: width 0.3s ease;
        }

        .fear { background: linear-gradient(90deg, #f85149, #d29922); }
        .neutral { background: var(--accent-yellow); }
        .greed { background: linear-gradient(90deg, #d29922, #3fb950); }

        .signal-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            margin-bottom: 10px;
        }

        .signal-buy { border-left: 3px solid var(--accent-green); }
        .signal-sell { border-left: 3px solid var(--accent-red); }

        .signal-asset {
            font-weight: 600;
        }

        .signal-type {
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 4px;
        }

        .signal-type.buy { background: rgba(63, 185, 80, 0.2); color: var(--accent-green); }
        .signal-type.sell { background: rgba(248, 81, 73, 0.2); color: var(--accent-red); }

        .confidence-bar {
            width: 60px;
            height: 4px;
            background: var(--bg-primary);
            border-radius: 2px;
            overflow: hidden;
        }

        .confidence-fill {
            height: 100%;
            background: var(--accent-blue);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.875rem;
        }

        .nav {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        .nav-link {
            padding: 8px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            text-decoration: none;
            font-size: 0.875rem;
        }

        .nav-link:hover, .nav-link.active {
            background: var(--bg-tertiary);
            border-color: var(--accent-blue);
        }

        .refresh-indicator {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .htmx-request .refresh-indicator::after {
            content: " Updating...";
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .live-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            animation: pulse 2s infinite;
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


def render_page(content: str, title: str = "Dashboard") -> str:
    """Render content within base template"""
    return BASE_HTML.replace("{content}", content)


# Mock data for demonstration
# In production, this would come from the actual services
MOCK_DATA = {
    "portfolio": {
        "total_value": 100.00,
        "daily_pnl": 0.00,
        "daily_pnl_pct": 0.00,
        "open_positions": 0
    },
    "sentiment": {
        "market": {"score": 45, "level": "fear", "trend": "stable"},
        "btc": {"score": 52, "level": "neutral", "trend": "improving"},
        "eth": {"score": 48, "level": "neutral", "trend": "stable"},
        "sol": {"score": 61, "level": "greed", "trend": "improving"}
    },
    "signals": [],
    "trades": [],
    "status": "paper"
}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    content = f"""
        <header>
            <div class="logo">CARBS</div>
            <div>
                <span class="live-dot"></span>
                <span class="status-badge status-{MOCK_DATA['status']}">{MOCK_DATA['status'].upper()}</span>
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
                        <div class="metric-value neutral">${MOCK_DATA['portfolio']['total_value']:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Today's P&L</div>
                        <div class="metric-value {'positive' if MOCK_DATA['portfolio']['daily_pnl'] >= 0 else 'negative'}">
                            ${MOCK_DATA['portfolio']['daily_pnl']:+.2f} ({MOCK_DATA['portfolio']['daily_pnl_pct']:+.2f}%)
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Open Positions</div>
                        <div class="metric-value neutral">{MOCK_DATA['portfolio']['open_positions']}</div>
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
                    {render_sentiment_widget()}
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
                    {render_signals_widget()}
                </div>
            </div>

            <!-- System Status Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">System Status</span>
                </div>
                <div id="status-content">
                    <div class="metric">
                        <div class="metric-label">Mode</div>
                        <div class="metric-value neutral">{MOCK_DATA['status'].upper()}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Last Update</div>
                        <div class="metric-value neutral" style="font-size: 1rem;">
                            {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Exchanges Connected</div>
                        <div class="metric-value neutral">0</div>
                    </div>
                </div>
            </div>
        </div>

        <footer>
            CARBS v1.0 | <span id="clock">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</span>
        </footer>
    """
    return HTMLResponse(render_page(content))


def render_sentiment_widget() -> str:
    """Render sentiment display widget"""
    html = ""
    for asset, data in MOCK_DATA["sentiment"].items():
        level_class = "fear" if data["score"] < 40 else "greed" if data["score"] > 60 else "neutral"
        html += f"""
            <div class="metric">
                <div class="metric-label">{asset.upper()}</div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="metric-value neutral" style="font-size: 1.25rem;">{data['score']}</span>
                    <span style="font-size: 0.75rem; color: var(--text-secondary);">{data['level']}</span>
                </div>
                <div class="sentiment-bar">
                    <div class="sentiment-fill {level_class}" style="width: {data['score']}%;"></div>
                </div>
            </div>
        """
    return html


def render_signals_widget() -> str:
    """Render active signals widget"""
    if not MOCK_DATA["signals"]:
        return """
            <div class="empty-state">
                <p>No active signals</p>
                <p style="font-size: 0.75rem; margin-top: 5px;">Signals will appear when opportunities are detected</p>
            </div>
        """

    html = ""
    for signal in MOCK_DATA["signals"]:
        signal_class = "signal-buy" if "buy" in signal["type"].lower() else "signal-sell"
        type_class = "buy" if "buy" in signal["type"].lower() else "sell"
        html += f"""
            <div class="signal-item {signal_class}">
                <div>
                    <span class="signal-asset">{signal['asset']}</span>
                    <span class="signal-type {type_class}">{signal['type']}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">Confidence</div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: {signal['confidence'] * 100}%;"></div>
                    </div>
                </div>
            </div>
        """
    return html


@app.get("/api/portfolio", response_class=HTMLResponse)
async def get_portfolio():
    """API endpoint for portfolio data (HTMX partial)"""
    return HTMLResponse(f"""
        <div class="metric">
            <div class="metric-label">Total Value</div>
            <div class="metric-value neutral">${MOCK_DATA['portfolio']['total_value']:.2f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Today's P&L</div>
            <div class="metric-value {'positive' if MOCK_DATA['portfolio']['daily_pnl'] >= 0 else 'negative'}">
                ${MOCK_DATA['portfolio']['daily_pnl']:+.2f} ({MOCK_DATA['portfolio']['daily_pnl_pct']:+.2f}%)
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Open Positions</div>
            <div class="metric-value neutral">{MOCK_DATA['portfolio']['open_positions']}</div>
        </div>
    """)


@app.get("/api/sentiment", response_class=HTMLResponse)
async def get_sentiment():
    """API endpoint for sentiment data (HTMX partial)"""
    return HTMLResponse(render_sentiment_widget())


@app.get("/api/signals", response_class=HTMLResponse)
async def get_signals():
    """API endpoint for signals (HTMX partial)"""
    return HTMLResponse(render_signals_widget())


@app.get("/signals", response_class=HTMLResponse)
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


@app.get("/trades", response_class=HTMLResponse)
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


@app.get("/settings", response_class=HTMLResponse)
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


def run_dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Run the dashboard server"""
    print(f"\n  CARBS Dashboard running at http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_dashboard()
