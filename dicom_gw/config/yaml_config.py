"""YAML-based configuration management for DICOM Gateway."""

import logging
import yaml
from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "dicom_gw"
    username: str = "dicom_gw"
    password: str = ""
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_acquire_timeout: int = 30
    echo: bool = False


class ApplicationConfig(BaseModel):
    """Application configuration."""
    name: str = "DICOM Gateway"
    version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    secret_key: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24


class DICOMStorageConfig(BaseModel):
    """DICOM storage configuration."""
    base_path: str = "/var/lib/dicom-gw/storage"
    study_path_template: str = "{study_instance_uid}"
    series_path_template: str = "{series_instance_uid}"
    instance_path_template: str = "{sop_instance_uid}.dcm"
    preserve_directory_structure: bool = True


class DICOMNetworkConfig(BaseModel):
    """DICOM network configuration."""
    local_ae_title: str = "DICOMGW"
    listen_port: int = 104
    max_pdu: int = 16384
    association_timeout: int = 30
    connection_timeout: int = 10


class TLSConfig(BaseModel):
    """TLS configuration."""
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    no_verify: bool = False
    cipher_suites: list[str] = Field(default_factory=lambda: [])


class SecurityConfig(BaseModel):
    """Security configuration."""
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special: bool = False
    account_lockout_attempts: int = 5
    account_lockout_duration_minutes: int = 30
    session_timeout_hours: int = 24
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 65536  # 64 MB
    argon2_parallelism: int = 4


class WorkerConfig(BaseModel):
    """Worker configuration."""
    queue_worker_poll_interval: float = 5.0
    queue_worker_batch_size: int = 10
    forwarder_worker_poll_interval: float = 5.0
    forwarder_worker_batch_size: int = 5
    dbpool_worker_flush_interval: float = 10.0
    dbpool_worker_batch_size: int = 100


class DestinationConfig(BaseModel):
    """Destination (AE) configuration."""
    name: str
    ae_title: str
    host: str
    port: int = 104
    max_pdu: int = 16384
    timeout: int = 30
    connection_timeout: int = 10
    tls_enabled: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    tls_ca_path: Optional[str] = None
    tls_no_verify: bool = False
    description: Optional[str] = None
    enabled: bool = True
    max_retries: int = 3
    retry_backoff_seconds: int = 60


class GatewayConfig(BaseModel):
    """Complete gateway configuration."""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    application: ApplicationConfig = Field(default_factory=ApplicationConfig)
    dicom_storage: DICOMStorageConfig = Field(default_factory=DICOMStorageConfig)
    dicom_network: DICOMNetworkConfig = Field(default_factory=DICOMNetworkConfig)
    tls: TLSConfig = Field(default_factory=TLSConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    workers: WorkerConfig = Field(default_factory=WorkerConfig)
    destinations: list[DestinationConfig] = Field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> "GatewayConfig":
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML configuration file
        
        Returns:
            GatewayConfig instance
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            config_data = {}
        
        return cls(**config_data)
    
    def to_yaml(self, config_path: Path) -> None:
        """Save configuration to YAML file.
        
        Args:
            config_path: Path to save YAML configuration file
        """
        config_data = self.model_dump(mode="json", exclude_none=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, indent=2)
    
    def merge_with_env(self, env_vars: Dict[str, str]) -> "GatewayConfig":
        """Merge configuration with environment variables.
        
        Environment variables take precedence over YAML config.
        Format: DICOM_GW_<SECTION>_<KEY> (e.g., DICOM_GW_DATABASE_HOST)
        
        Args:
            env_vars: Dictionary of environment variables
        
        Returns:
            New GatewayConfig instance with merged values
        """
        config_dict = self.model_dump(mode="json")
        
        # Map environment variables to config structure
        env_prefix = "DICOM_GW_"
        for key, value in env_vars.items():
            if not key.startswith(env_prefix):
                continue
            
            # Remove prefix and split
            parts = key[len(env_prefix):].lower().split("_")
            
            # Navigate config structure
            current = config_dict
            for part in parts[:-1]:
                if part not in current:
                    break
                current = current[part]
            else:
                # Convert value based on type
                final_key = parts[-1]
                if final_key in current:
                    # Try to convert to appropriate type
                    if isinstance(current[final_key], bool):
                        current[final_key] = value.lower() in ("true", "1", "yes")
                    elif isinstance(current[final_key], int):
                        try:
                            current[final_key] = int(value)
                        except ValueError:
                            logger.warning(f"Could not convert {key} to int: {value}")
                    elif isinstance(current[final_key], float):
                        try:
                            current[final_key] = float(value)
                        except ValueError:
                            logger.warning(f"Could not convert {key} to float: {value}")
                    elif isinstance(current[final_key], list):
                        # Handle comma-separated lists
                        current[final_key] = [item.strip() for item in value.split(",")]
                    else:
                        current[final_key] = value
        
        return GatewayConfig(**config_dict)
    
    def get_destination_by_name(self, name: str) -> Optional[DestinationConfig]:
        """Get destination configuration by name.
        
        Args:
            name: Destination name
        
        Returns:
            DestinationConfig or None if not found
        """
        for dest in self.destinations:
            if dest.name == name:
                return dest
        return None
    
    def get_destination_by_ae_title(self, ae_title: str) -> Optional[DestinationConfig]:
        """Get destination configuration by AE title.
        
        Args:
            ae_title: AE title
        
        Returns:
            DestinationConfig or None if not found
        """
        for dest in self.destinations:
            if dest.ae_title == ae_title:
                return dest
        return None


class ConfigManager:
    """Configuration manager for loading and managing gateway configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to YAML configuration file (optional)
        """
        self.config_path = config_path or Path("/etc/dicom-gw/config.yaml")
        self.config: Optional[GatewayConfig] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                self.config = GatewayConfig.from_yaml(self.config_path)
                logger.info("Loaded configuration from %s", self.config_path)
            except Exception as e:
                logger.warning("Failed to load configuration from %s: %s", self.config_path, e)
                logger.info("Using default configuration")
                self.config = GatewayConfig()
        else:
            logger.info("Configuration file not found at %s, using defaults", self.config_path)
            self.config = GatewayConfig()
    
    def reload(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        self._load_config()
        logger.info("Configuration reloaded")
    
    def save(self, config_path: Optional[Path] = None) -> None:
        """Save current configuration to file.
        
        Args:
            config_path: Path to save configuration (defaults to current config_path)
        """
        save_path = config_path or self.config_path
        
        # Create parent directory if it doesn't exist
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config:
            self.config.to_yaml(save_path)
            logger.info("Saved configuration to %s", save_path)
    
    def get_config(self) -> GatewayConfig:
        """Get current configuration.
        
        Returns:
            GatewayConfig instance
        """
        if self.config is None:
            self.config = GatewayConfig()
        return self.config
    
    def update_destination(self, destination: DestinationConfig) -> None:
        """Update or add a destination configuration.
        
        Args:
            destination: Destination configuration
        """
        if self.config is None:
            self.config = GatewayConfig()
        
        # Find existing destination
        for i, dest in enumerate(self.config.destinations):
            if dest.name == destination.name:
                self.config.destinations[i] = destination
                logger.info("Updated destination: %s", destination.name)
                return
        
        # Add new destination
        self.config.destinations.append(destination)
        logger.info("Added destination: %s", destination.name)
    
    def remove_destination(self, name: str) -> bool:
        """Remove a destination configuration.
        
        Args:
            name: Destination name
        
        Returns:
            True if destination was removed, False if not found
        """
        if self.config is None:
            return False
        
        for i, dest in enumerate(self.config.destinations):
            if dest.name == name:
                del self.config.destinations[i]
                logger.info("Removed destination: %s", name)
                return True
        
        return False


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """Get the global configuration manager instance.
    
    Args:
        config_path: Optional path to configuration file
    
    Returns:
        ConfigManager instance
    """
    global _config_manager  # noqa: PLW0603
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager

