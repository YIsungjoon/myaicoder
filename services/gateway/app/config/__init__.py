from .settings import (
    AuthConfig,
    ConcurrencyConfig,
    DatabaseConfig,
    GatewayConfig,
    LoggingConfig,
    ModelsConfig,
    RateLimitConfig,
    RoleLimitConfig,
    RouteConfig,
    ServerConfig,
    UserConfig,
    UserOverrideConfig,
)

# Singleton instance for the gateway service
config = GatewayConfig.load()
