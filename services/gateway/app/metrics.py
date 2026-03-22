# Backward compatibility - moved to infra/metrics.py
from .infra.metrics import (  # noqa: F401
    ACTIVE_REQUESTS,
    ERROR_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    TOKENS_TOTAL,
    TTFT,
)
