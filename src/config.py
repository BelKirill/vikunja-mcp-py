"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Vikunja configuration
    vikunja_url: str
    vikunja_token: str

    # Vertex AI configuration
    gcp_project: str | None = None
    gcp_location: str = "us-central1"
    gemini_model: str = "gemini-2.0-flash"

    # Server configuration
    log_level: str = "INFO"


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
