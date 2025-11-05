"""Application settings and configuration management."""

import os
import logging
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config files."""
    
    model_config = SettingsConfigDict(
        env_file=[
            ".env",
            "/etc/dicom-gw/dicom-gw-api.env",
            "/etc/dicom-gw/dicom-gw-workers.env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw",
        description="PostgreSQL database URL (asyncpg format)"
    )
    database_pool_min: int = Field(default=4, ge=1, le=100)
    database_pool_max: int = Field(default=32, ge=1, le=200)
    database_pool_acquire_timeout: int = Field(default=30, ge=1)
    
    # Application
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=False)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = Field(default="/api/v1")
    
    # DICOM Storage Paths
    dicom_storage_path: str = Field(default="/var/lib/dicom-gw")
    dicom_incoming_path: str = Field(default="/var/lib/dicom-gw/incoming")
    dicom_queue_path: str = Field(default="/var/lib/dicom-gw/queue")
    dicom_forwarded_path: str = Field(default="/var/lib/dicom-gw/forwarded")
    dicom_failed_path: str = Field(default="/var/lib/dicom-gw/failed")
    dicom_tmp_path: str = Field(default="/var/lib/dicom-gw/tmp")
    
    # DICOM Network
    dicom_ae_title: str = Field(default="GATEWAY", max_length=16)
    dicom_port: int = Field(default=104, ge=1, le=65535)
    dicom_max_pdu: int = Field(default=16384, ge=128)
    dicom_timeout: int = Field(default=30, ge=1)
    
    # Security
    secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24, ge=1)
    argon2_time_cost: int = Field(default=3, ge=1, le=10)
    argon2_memory_cost: int = Field(default=65536, ge=1024)
    argon2_parallelism: int = Field(default=4, ge=1, le=16)
    
    # TLS
    tls_enabled: bool = Field(default=True)
    tls_cert_path: Optional[str] = Field(default=None)
    tls_key_path: Optional[str] = Field(default=None)
    tls_ca_path: Optional[str] = Field(default=None)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text
    log_file: Optional[str] = Field(default=None)
    
    # Metrics
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1, le=65535)
    
    @field_validator("dicom_storage_path", "dicom_incoming_path", "dicom_queue_path", 
                     "dicom_forwarded_path", "dicom_failed_path", "dicom_tmp_path")
    @classmethod
    def validate_paths(cls, v: str) -> str:
        """Validate and normalize storage paths."""
        path = Path(v)
        # In production, ensure paths are absolute
        if not path.is_absolute() and os.getenv("APP_ENV") == "production":
            raise ValueError(f"Storage path must be absolute in production: {v}")
        return str(path.resolve())
    
    @field_validator("dicom_ae_title")
    @classmethod
    def validate_ae_title(cls, v: str) -> str:
        """Validate AE Title format (max 16 characters)."""
        if len(v) > 16:
            raise ValueError("AE Title must be 16 characters or less")
        return v.upper()
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env.lower() == "development"


# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Get the global settings instance (singleton).
    
    Args:
        config_path: Optional path to YAML config file
    
    Returns:
        Settings instance
    """
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
        
        # Try to load from YAML config if available
        if config_path is None:
            config_path = Path("/etc/dicom-gw/config.yaml")
        
        # Check if DATABASE_URL is set in environment - if so, use it and skip YAML URL construction
        env_database_url = os.getenv("DATABASE_URL")
        if env_database_url:
            _settings.database_url = env_database_url
        
        if config_path.exists():
            try:
                from dicom_gw.config.yaml_config import get_config_manager
                config_manager = get_config_manager(config_path)
                yaml_config = config_manager.get_config()
                
                # Merge YAML config into settings
                # This allows environment variables to override YAML
                if yaml_config.database:
                    # Only construct database_url from YAML if DATABASE_URL env var is not set
                    if not env_database_url:
                        # Use existing password from environment if available
                        db_password = os.getenv("DICOM_GW_DATABASE_PASSWORD", "")
                        if not db_password and yaml_config.database.password:
                            db_password = yaml_config.database.password
                        
                        _settings.database_url = (
                            f"postgresql+asyncpg://{yaml_config.database.username}:"
                            f"{db_password}@{yaml_config.database.host}:"
                            f"{yaml_config.database.port}/{yaml_config.database.database}"
                        )
                    _settings.database_pool_min = yaml_config.database.pool_min_size
                    _settings.database_pool_max = yaml_config.database.pool_max_size
                    _settings.database_pool_acquire_timeout = yaml_config.database.pool_acquire_timeout
                
                if yaml_config.application:
                    # app_name not in Settings model, skip
                    _settings.app_debug = yaml_config.application.debug
                    _settings.api_prefix = yaml_config.application.api_prefix
                    _settings.app_host = yaml_config.application.api_host
                    _settings.app_port = yaml_config.application.api_port
                    if yaml_config.application.jwt_secret_key:
                        _settings.secret_key = yaml_config.application.jwt_secret_key
                    _settings.jwt_algorithm = yaml_config.application.jwt_algorithm
                    _settings.jwt_expiration_hours = yaml_config.application.jwt_expiration_hours
                
                if yaml_config.dicom_storage:
                    _settings.dicom_storage_path = yaml_config.dicom_storage.base_path
                
                if yaml_config.dicom_network:
                    _settings.dicom_ae_title = yaml_config.dicom_network.local_ae_title
                    _settings.dicom_port = yaml_config.dicom_network.listen_port
                    _settings.dicom_max_pdu = yaml_config.dicom_network.max_pdu
                
                if yaml_config.security:
                    _settings.argon2_time_cost = yaml_config.security.argon2_time_cost
                    _settings.argon2_memory_cost = yaml_config.security.argon2_memory_cost
                    _settings.argon2_parallelism = yaml_config.security.argon2_parallelism
                
                logger.info("Loaded settings from YAML config: %s", config_path)
            except Exception as e:
                logger.warning("Failed to load YAML config: %s, using environment variables/defaults", e)
    
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment/config files."""
    global _settings
    _settings = Settings()
    return _settings

