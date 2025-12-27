"""Configuration for celery-flow library."""

from pydantic import BaseModel, ConfigDict


class CeleryFlowConfig(BaseModel):
    """Frozen configuration for celery-flow initialization."""

    model_config = ConfigDict(frozen=True)

    transport_url: str
    prefix: str = "celery_flow"
    ttl: int = 86400
    redact_args: bool = True


_config: CeleryFlowConfig | None = None


def get_config() -> CeleryFlowConfig | None:
    """Get the active configuration, or None if not initialized."""
    return _config


def set_config(config: CeleryFlowConfig) -> None:
    """Set the active configuration."""
    global _config
    _config = config
