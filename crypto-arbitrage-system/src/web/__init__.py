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

Module Structure:
- templates.py: HTML templates and render functions
- data.py: Data fetching and defaults
- routes.py: FastAPI route handlers
"""

import logging
import uvicorn
from fastapi import FastAPI

from .templates import BASE_HTML, render_page
from .data import DEFAULT_DATA, MOCK_DATA, get_dashboard_data
from .routes import router, render_sentiment_widget, render_signals_widget

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CARBS Dashboard",
    description="Crypto Arbitrage System Dashboard",
    version="1.0.0"
)

# Include routes
app.include_router(router)


def run_dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Run the dashboard server"""
    logger.info(f"CARBS Dashboard starting at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


__all__ = [
    # App
    "app",
    "run_dashboard",

    # Templates
    "BASE_HTML",
    "render_page",

    # Data
    "DEFAULT_DATA",
    "MOCK_DATA",
    "get_dashboard_data",

    # Widgets
    "render_sentiment_widget",
    "render_signals_widget",
]
