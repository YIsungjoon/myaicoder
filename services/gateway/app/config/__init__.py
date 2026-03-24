from .settings import (
    AuthConfig as AuthConfig,
    ConcurrencyConfig as ConcurrencyConfig,
    DatabaseConfig as DatabaseConfig,
    GatewayConfig,
    LoggingConfig as LoggingConfig,
    ModelsConfig as ModelsConfig,
    RateLimitConfig as RateLimitConfig,
    RoleLimitConfig as RoleLimitConfig,
    RouteConfig as RouteConfig,
    ServerConfig as ServerConfig,
    UserConfig as UserConfig,
    UserOverrideConfig as UserOverrideConfig,
)

# Singleton instance for the gateway service
config = GatewayConfig.load()
