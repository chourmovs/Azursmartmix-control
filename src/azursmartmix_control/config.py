# src/azursmartmix_control/config.py
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Compose file (read-only mount) used for display env panel (legacy / read-only)
    compose_path: str = Field(default="/compose/docker-compose.yml", alias="COMPOSE_PATH")
    compose_service_engine: str = Field(default="azursmartmix_engine", alias="COMPOSE_SERVICE_ENGINE")
    compose_service_scheduler: str = Field(default="azursmartmix_scheduler", alias="COMPOSE_SERVICE_SCHEDULER")

    # Host project directory (mounted into control container)
    azuramix_dir: str = Field(default="/var/azuramix", alias="AZURAMIX_DIR")
    azuramix_compose_file: str = Field(default="/var/azuramix/docker-compose.yml", alias="AZURAMIX_COMPOSE_FILE")

    # Host env file (the only file we edit for settings)
    azuramix_env_file: str = Field(default="/var/azuramix/azuramix.env", alias="AZURAMIX_ENV_FILE")

    # Mounted config path used by the mountpoints manager
    azuramix_config_dir: str = Field(default="/azuramix/config", alias="AZURAMIX_CONFIG_DIR")
    azuramix_config_file: str = Field(default="/azuramix/config/config.yml", alias="AZURAMIX_CONFIG_FILE")

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
    icecast_public_url: str = Field(
        default="http://chourmovs.ddnsfree.com:8000/gst-test.mp3",
        alias="ICECAST_PUBLIC_URL",
    )

    # Default image ref (fallback for update)
    azursmartmix_image: str = Field(default="chourmovs/azursmartmix:beta1", alias="AZURSMARTMIX_IMAGE")

    # Image repo base for dynamic tag selection
    azursmartmix_repo: str = Field(default="chourmovs/azursmartmix", alias="AZURSMARTMIX_REPO")

    # ------------------------------------------------------------------
    # AzuraCast control plane access (NEW - read-only integration layer)
    # ------------------------------------------------------------------
    # NOTE:
    # - Values are expected to be injected via env_file (/var/azuramix/azuramix.env)
    # - Defaults are conservative and match typical AzuraCast docker network
    # - No hard dependency: empty API key => calls will fail gracefully (403)
    # ------------------------------------------------------------------

    azuracast_base_url: str = Field(
        default="http://web",
        alias="AZURACAST_BASE_URL",
    )

    azuracast_api_key: str = Field(
        default="",
        alias="AZURACAST_API_KEY",
    )

    azuracast_station_id: int = Field(
        default=1,
        alias="AZURACAST_STATION_ID",
    )

    azuracast_timeout_s: float = Field(
        default=10.0,
        alias="AZURACAST_TIMEOUT_S",
    )

    azuracast_verify_tls: bool = Field(
        default=False,
        alias="AZURACAST_VERIFY_TLS",
    )


def get_settings() -> Settings:
    return Settings()
