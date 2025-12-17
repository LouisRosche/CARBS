"""
Web Templates

HTML templates for the dashboard.
"""

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

        .signal-asset { font-weight: 600; }

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
