"""Prometheus metrics definitions for Gateway observability."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# -- Request metrics (middleware) --
REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
ACTIVE_REQUESTS = Gauge(
    "gateway_active_requests",
    "Currently active requests",
)

# -- Streaming metrics (proxy.py finally block) --
REQUEST_LATENCY = Histogram(
    "gateway_request_latency_seconds",
    "Total request duration (stream completion included)",
    ["method", "path", "is_stream"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
TTFT = Histogram(
    "gateway_ttft_seconds",
    "Time to first token (streaming only)",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0],
)
TOKENS_TOTAL = Counter(
    "gateway_tokens_total",
    "Token usage",
    ["model", "type"],
)

# -- Error metrics --
ERROR_COUNT = Counter(
    "gateway_errors_total",
    "Total errors by type",
    ["type"],
)
