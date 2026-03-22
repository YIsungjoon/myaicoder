# Backward compatibility - moved to middleware/deps.py
from .middleware.deps import (  # noqa: F401
    check_concurrency,
    check_rate_limit,
    get_auth_store,
    get_current_user,
    get_raw_api_key,
)
