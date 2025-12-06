"""Prometheus metrics collector"""
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self, port=8000):
        self.port = port

        # Counters
        self.opportunities_found = Counter(
            'arbitrage_opportunities_total',
            'Total opportunities found'
        )
        self.orderbooks_fetched = Counter(
            'orderbooks_fetched_total',
            'Total orderbooks fetched'
        )
        self.orderbook_cache_hits = Counter(
            'orderbook_cache_hits_total',
            'Total orderbook cache hits'
        )
        self.orderbook_errors = Counter(
            'orderbook_errors_total',
            'Total orderbook fetch errors'
        )
        self.executions_total = Counter(
            'executions_total',
            'Total trade executions attempted'
        )
        self.executions_successful = Counter(
            'executions_successful_total',
            'Total successful trade executions'
        )

        # Gauges
        self.current_spread = Gauge(
            'current_spread_bps',
            'Current best spread in basis points',
            ['symbol']
        )
        self.portfolio_value = Gauge(
            'portfolio_value_usd',
            'Current portfolio value in USD'
        )

        # Histograms
        self.execution_time = Histogram(
            'execution_time_ms',
            'Trade execution time in milliseconds',
            buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
        )

        try:
            start_http_server(port)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")

    def increment(self, metric_name, value=1):
        """Increment a counter metric"""
        if hasattr(self, metric_name):
            metric = getattr(self, metric_name)
            if hasattr(metric, 'inc'):
                metric.inc(value)

    def set_gauge(self, metric_name, value, labels=None):
        """Set a gauge metric value"""
        if hasattr(self, metric_name):
            metric = getattr(self, metric_name)
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)

    def observe(self, metric_name, value):
        """Record a histogram observation"""
        if hasattr(self, metric_name):
            metric = getattr(self, metric_name)
            if hasattr(metric, 'observe'):
                metric.observe(value)
