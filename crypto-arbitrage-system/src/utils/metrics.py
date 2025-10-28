"""Prometheus metrics collector"""
from prometheus_client import Counter, Gauge, start_http_server
import logging

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, port=8000):
        self.port = port
        self.opportunities = Counter('arbitrage_opportunities_total', 'Total opportunities found')
        self.orderbooks = Counter('orderbooks_fetched_total', 'Total orderbooks fetched')
        start_http_server(port)
        logger.info(f"Metrics server started on port {port}")
    
    def increment(self, metric_name, value=1):
        if hasattr(self, metric_name):
            getattr(self, metric_name).inc(value)
