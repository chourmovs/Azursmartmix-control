from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Runtime settings for the control plane."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # API wiring
    api_prefix: str = Field(default="/api", alias="API_PREFIX")

    # UI bind
    ui_host: str = Field(default="0.0.0.0", alias="UI_HOST")
    ui_port: int = Field(default=8088, alias="UI_PORT")

    # Targets (Docker containers)
    engine_container: str = Field(default="azursmartmix_engine", alias="ENGINE_CONTAINER")
    scheduler_container: str = Field(default="azursmartmix_scheduler", alias="SCHEDULER_CONTAINER")

    # Scheduler API base URL
    sched_base_url: str = Field(default="http://azursmartmix_scheduler:8001", alias="SCHED_BASE_URL")

    # Compose file (read-only mount) used for display env panel
    compose_path: str = Field(default="/compose/docker-compose.yml", alias="COMPOSE_PATH")
    compose_service_engine: str = Field(default="azursmartmix_engine", alias="COMPOSE_SERVICE_ENGINE")
    compose_service_scheduler: str = Field(default="azursmartmix_scheduler", alias="COMPOSE_SERVICE_SCHEDULER")

    # NEW: Host project directory (mounted into control container)
    azuramix_dir: str = Field(default="/var/azuramix", alias="AZURAMIX_DIR")
    azuramix_compose_file: str = Field(default="/var/azuramix/docker-compose.yml", alias="AZURAMIX_COMPOSE_FILE")

    # Icecast now-playing
    icecast_scheme: str = Field(default="http", alias="ICECAST_SCHEME")
    icecast_host: str = Field(default="web", alias="ICECAST_HOST")
    icecast_port: int = Field(default=8000, alias="ICECAST_PORT")
    icecast_mount: str = Field(default="/gst-test.mp3", alias="ICECAST_MOUNT")
    icecast_status_path: str = Field(default="/status-json.xsl", alias="ICECAST_STATUS_PATH")

    # Logs
    log_tail_lines_default: int = Field(default=400, alias="LOG_TAIL_LINES_DEFAULT")
    log_tail_lines_max: int = Field(default=2000, alias="LOG_TAIL_LINES_MAX")

    # Public stream URL (UI player)
    icecast_public_url: str = Field(default="http://chourmovs.ddnsfree.com:8000/gst-test.mp3", alias="ICECAST_PUBLIC_URL")

    # Default image ref (fallback for update)
    azursmartmix_image: str = Field(default="chourmovs/azursmartmix:beta1", alias="AZURSMARTMIX_IMAGE")

    # Image repo base for dynamic tag selection
    azursmartmix_repo: str = Field(default="chourmovs/azursmartmix", alias="AZURSMARTMIX_REPO")


def get_settings() -> Settings:
    return Settings()
