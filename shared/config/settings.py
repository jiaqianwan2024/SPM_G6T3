"""Settings every microservice shares.

Each service subclasses this and supplies its own database URL, plus any
URLs or numbers that belong only to that service.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Comma-separated; browsers treat localhost and 127.0.0.1 as distinct origins.
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Shared secret for service-to-service calls that have no user token to forward.
    # Empty means such calls are refused. Set INTERNAL_SERVICE_KEY the same on every service.
    internal_service_key: str = ""
