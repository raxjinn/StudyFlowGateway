"""Configuration management endpoints."""

import logging
import yaml
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from dicom_gw.api.dependencies import RequireAdmin
from dicom_gw.config.yaml_config import (
    get_config_manager,
    GatewayConfig,
    DestinationConfig,
)
from fastapi import Form

logger = logging.getLogger(__name__)

router = APIRouter()


class ConfigReloadResponse(BaseModel):
    """Configuration reload response."""
    message: str
    config_path: str


@router.post("/config/reload", response_model=ConfigReloadResponse)
async def reload_config(current_user=Depends(RequireAdmin)):  # noqa: ARG001
    """Reload configuration from file."""
    try:
        config_manager = get_config_manager()
        config_manager.reload()
        
        return ConfigReloadResponse(
            message="Configuration reloaded successfully",
            config_path=str(config_manager.config_path),
        )
    except Exception as e:
        logger.error("Failed to reload configuration: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload configuration: {str(e)}",
        ) from e


@router.get("/config")
async def get_config(current_user=Depends(RequireAdmin)):  # noqa: ARG001
    """Get current configuration (excluding sensitive fields)."""
    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        
        # Convert to dict and redact sensitive fields
        config_dict = config.model_dump(mode="json")
        
        # Redact passwords and keys
        if "database" in config_dict:
            config_dict["database"]["password"] = "***REDACTED***"
        if "application" in config_dict:
            config_dict["application"]["secret_key"] = "***REDACTED***"
            config_dict["application"]["jwt_secret_key"] = "***REDACTED***"
        
        return {
            "config": config_dict,
            "config_path": str(config_manager.config_path),
        }
    except Exception as e:
        logger.error("Failed to get configuration: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration: {str(e)}",
        ) from e


@router.post("/config/upload")
async def upload_config_file(
    file: UploadFile = File(...),
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Upload a new configuration file.
    
    This will replace the current configuration file.
    """
    try:
        # Validate file extension
        if not file.filename or not file.filename.endswith((".yaml", ".yml")):
            raise HTTPException(
                status_code=400,
                detail="Configuration file must be a YAML file (.yaml or .yml)",
            )
        
        # Read file content
        content = await file.read()
        
        # Parse and validate YAML
        config_data = yaml.safe_load(content)
        
        if not config_data:
            raise HTTPException(
                status_code=400,
                detail="Configuration file is empty or invalid",
            )
        
        # Validate configuration structure
        try:
            config = GatewayConfig(**config_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration: {str(e)}",
            ) from e
        
        # Save configuration
        config_manager = get_config_manager()
        config_path = config_manager.config_path
        
        # Create backup
        backup_path = Path(f"{config_path}.backup")
        if config_path.exists():
            shutil.copy(config_path, backup_path)
            logger.info("Created backup: %s", backup_path)
        
        # Write new configuration
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_bytes(content)
        
        # Reload configuration
        config_manager.reload()
        
        return {
            "message": "Configuration file uploaded and reloaded successfully",
            "config_path": str(config_path),
            "backup_path": str(backup_path) if backup_path.exists() else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload configuration: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload configuration: {str(e)}",
        ) from e


@router.get("/config/destinations")
async def get_destinations_config(current_user=Depends(RequireAdmin)):  # noqa: ARG001
    """Get destinations configuration."""
    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        
        return {
            "destinations": [
                dest.model_dump(mode="json") for dest in config.destinations
            ],
        }
    except Exception as e:
        logger.error("Failed to get destinations config: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get destinations configuration: {str(e)}",
        ) from e


@router.post("/config/destinations")
async def add_destination(
    destination: DestinationConfig,
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Add or update a destination configuration."""
    try:
        config_manager = get_config_manager()
        config_manager.update_destination(destination)
        
        # Save configuration
        config_manager.save()
        
        return {
            "message": "Destination configuration updated",
            "destination": destination.model_dump(mode="json"),
        }
    except Exception as e:
        logger.error("Failed to update destination: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update destination: {str(e)}",
        ) from e


@router.delete("/config/destinations/{name}")
async def delete_destination(
    name: str,
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Delete a destination configuration."""
    try:
        config_manager = get_config_manager()
        
        if not config_manager.remove_destination(name):
            raise HTTPException(
                status_code=404,
                detail=f"Destination not found: {name}",
            )
        
        # Save configuration
        config_manager.save()
        
        return {"message": f"Destination '{name}' removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete destination: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete destination: {str(e)}",
        ) from e


@router.post("/certs/upload")
async def upload_certificate(
    cert_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    ca_file: Optional[UploadFile] = File(None),
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Upload TLS certificates."""
    from dicom_gw.security.tls import get_certificate_manager
    
    try:
        # Read file contents
        cert_content = await cert_file.read()
        key_content = await key_file.read()
        ca_content = await ca_file.read() if ca_file else None
        
        # Upload certificates
        cert_manager = get_certificate_manager()
        success = cert_manager.upload_certificate(cert_content, key_content, ca_content)
        
        if success:
            return {
                "status": "success",
                "message": "Certificates uploaded successfully",
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to upload certificates. Check logs for details.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload certificates: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload certificates: {str(e)}",
        ) from e


@router.post("/certs/letsencrypt/provision")
async def provision_letsencrypt(
    domain: str = Form(...),
    email: str = Form(...),
    webroot_path: Optional[str] = Form(None),
    staging: bool = Form(False),
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Provision Let's Encrypt certificate."""
    from dicom_gw.security.tls import get_certificate_manager
    from pydantic import BaseModel
    
    class ProvisionResponse(BaseModel):
        status: str
        message: str
        certificate_info: Optional[dict] = None
    
    try:
        cert_manager = get_certificate_manager()
        success = cert_manager.provision_letsencrypt(
            domain=domain,
            email=email,
            webroot_path=webroot_path,
            staging=staging,
        )
        
        if success:
            cert_info = cert_manager.get_certificate_info()
            return ProvisionResponse(
                status="success",
                message=f"Let's Encrypt certificate provisioned for {domain}",
                certificate_info=cert_info,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to provision Let's Encrypt certificate. Check logs for details.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to provision Let's Encrypt certificate: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision certificate: {str(e)}",
        ) from e


@router.post("/certs/letsencrypt/renew")
async def renew_letsencrypt(
    domain: Optional[str] = None,
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Renew Let's Encrypt certificate."""
    from dicom_gw.security.tls import get_certificate_manager
    
    try:
        cert_manager = get_certificate_manager()
        success = cert_manager.renew_certificate(domain=domain)
        
        if success:
            cert_info = cert_manager.get_certificate_info()
            return {
                "status": "success",
                "message": "Certificate renewed successfully",
                "certificate_info": cert_info,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to renew certificate. Check logs for details.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to renew certificate: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to renew certificate: {str(e)}",
        ) from e


@router.get("/certs/info")
async def get_certificate_info(
    current_user=Depends(RequireAdmin),  # noqa: ARG001
):
    """Get current certificate information."""
    from dicom_gw.security.tls import get_certificate_manager
    
    try:
        cert_manager = get_certificate_manager()
        cert_info = cert_manager.get_certificate_info()
        
        if cert_info:
            return {
                "status": "success",
                "certificate": cert_info,
            }
        else:
            return {
                "status": "not_found",
                "message": "No certificate found",
            }
    
    except Exception as e:
        logger.error("Failed to get certificate info: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get certificate info: {str(e)}",
        ) from e
