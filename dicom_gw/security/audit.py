"""Audit logging system for security and compliance."""

import logging
import uuid
from typing import Optional, Dict, Any
from functools import wraps

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import AuditLog

logger = logging.getLogger(__name__)


async def log_audit_event(
    action: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Log an audit event to the database.
    
    This function creates an append-only audit log entry that cannot be modified
    after creation, ensuring compliance and security.
    
    Args:
        action: Action performed (e.g., "login", "create_destination", "forward_study")
        user_id: User ID who performed the action
        username: Username who performed the action
        ip_address: IP address of the client
        user_agent: User agent string
        resource_type: Type of resource affected (e.g., "study", "destination")
        resource_id: ID of the resource affected
        status: Status of the action ("success", "failure", "denied")
        error_message: Error message if action failed
        metadata: Additional metadata as dictionary
    
    Returns:
        Audit log entry ID if successful, None otherwise
    """
    try:
        audit_id = uuid.uuid4()
        
        async for session in get_db_session():
            audit_log = AuditLog(
                id=audit_id,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                error_message=error_message,
                audit_metadata=metadata,
            )
            
            session.add(audit_log)
            await session.commit()
            
            logger.debug("Audit event logged: %s by %s", action, username or "unknown")
            break
        
        return str(audit_id)
    
    except Exception as e:
        logger.error("Failed to log audit event: %s", e, exc_info=True)
        return None


def audit_log(
    action: str,
    resource_type: Optional[str] = None,
):
    """Decorator to automatically log audit events for API endpoints.
    
    Args:
        action: Action name to log
        resource_type: Type of resource (optional, will try to infer from route)
    
    Example:
        @audit_log("create_destination", resource_type="destination")
        async def create_destination(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import Request
            
            # Try to get request and user from arguments
            request: Optional[Request] = None
            user = None
            
            # Find Request object in args/kwargs
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                request = kwargs.get("request")
            
            # Try to get current user
            try:
                # Check if current_user is in kwargs (from dependencies)
                if "current_user" in kwargs:
                    user = kwargs["current_user"]
                # Try to get from dependencies
                elif hasattr(func, "__annotations__"):
                    # This is a simplified approach - in practice, we'd need to
                    # properly resolve FastAPI dependencies
                    pass
            except Exception:
                pass
            
            # Extract resource_id from path parameters if available
            resource_id = None
            if request:
                # Try to get resource ID from path parameters
                if hasattr(request, "path_params"):
                    resource_id = request.path_params.get("destination_id") or \
                                 request.path_params.get("study_id") or \
                                 request.path_params.get("user_id")
            
            # Get IP address and user agent
            ip_address = None
            user_agent = None
            if request:
                if hasattr(request, "client"):
                    ip_address = request.client.host if request.client else None
                if hasattr(request, "headers"):
                    user_agent = request.headers.get("user-agent")
            
            # Execute the function
            status_value = "success"
            error_message = None
            result = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_value = "failure"
                error_message = str(e)
                raise
            finally:
                # Log the audit event
                await log_audit_event(
                    action=action,
                    user_id=str(user.id) if user and hasattr(user, "id") else None,
                    username=user.username if user and hasattr(user, "username") else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status=status_value,
                    error_message=error_message,
                    metadata={"function": func.__name__} if result else None,
                )
        
        return wrapper
    return decorator


async def log_login_attempt(
    username: str,
    success: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    error_message: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Log a login attempt.
    
    Args:
        username: Username attempted
        success: Whether login was successful
        ip_address: IP address of client
        user_agent: User agent string
        error_message: Error message if failed
        user_id: User ID if successful
    """
    await log_audit_event(
        action="login",
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        status="success" if success else "failure",
        error_message=error_message,
    )


async def log_config_change(
    user_id: str,
    username: str,
    change_type: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None,
):
    """Log a configuration change.
    
    Args:
        user_id: User ID making the change
        username: Username making the change
        change_type: Type of change (e.g., "update_destination", "reload_config")
        details: Details of the change
        ip_address: IP address of client
    """
    await log_audit_event(
        action=change_type,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        resource_type="config",
        status="success",
        metadata=details,
    )


async def log_forward_action(
    user_id: Optional[str],
    username: Optional[str],
    study_instance_uid: str,
    destination_name: str,
    success: bool,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
):
    """Log a study forwarding action.
    
    Args:
        user_id: User ID initiating forward
        username: Username initiating forward
        study_instance_uid: Study Instance UID
        destination_name: Destination name
        success: Whether forward was successful
        error_message: Error message if failed
        ip_address: IP address of client
    """
    await log_audit_event(
        action="forward_study",
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        resource_type="study",
        resource_id=study_instance_uid,
        status="success" if success else "failure",
        error_message=error_message,
        metadata={"destination": destination_name},
    )


async def log_user_action(
    action: str,
    user_id: str,
    username: str,
    target_user_id: Optional[str] = None,
    target_username: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
):
    """Log a user management action.
    
    Args:
        action: Action type (e.g., "create_user", "update_user", "delete_user")
        user_id: User ID performing the action
        username: Username performing the action
        target_user_id: Target user ID (if applicable)
        target_username: Target username (if applicable)
        success: Whether action was successful
        error_message: Error message if failed
        ip_address: IP address of client
    """
    await log_audit_event(
        action=action,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        resource_type="user",
        resource_id=target_user_id,
        status="success" if success else "failure",
        error_message=error_message,
        metadata={"target_username": target_username} if target_username else None,
    )

