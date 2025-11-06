"""FastAPI dependencies for authentication and authorization."""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from dicom_gw.database.models import User
from dicom_gw.database.connection import get_db_session
from dicom_gw.security.auth import decode_access_token
from dicom_gw.security.rbac import Permission, has_permission, require_role, Role
from sqlalchemy import select

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency to get current authenticated user.
    
    Args:
        token: JWT token from request
    
    Returns:
        User database object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Convert string ID to UUID
    try:
        from uuid import UUID
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    
    async for session in get_db_session():
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or disabled",
            )
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is locked",
            )
        
        return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (dependency).
    
    Args:
        current_user: Current user from token
    
    Returns:
        User object if active
    
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return current_user


def require_permission(permission: Permission):
    """Dependency factory for requiring a specific permission.
    
    Args:
        permission: Required permission
    
    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}",
            )
        return current_user
    
    return permission_checker


def require_role_dependency(required_role: Role):
    """Dependency factory for requiring a specific role.
    
    Args:
        required_role: Minimum required role
    
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not require_role(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {required_role.value}",
            )
        return current_user
    
    return role_checker


# Common permission dependencies
RequireAdmin = require_role_dependency(Role.ADMIN)
RequireOperator = require_role_dependency(Role.OPERATOR)

# Common permission dependencies
RequireViewStudies = require_permission(Permission.VIEW_STUDIES)
RequireManageStudies = require_permission(Permission.MANAGE_STUDIES)
RequireManageDestinations = require_permission(Permission.MANAGE_DESTINATIONS)
RequireManageConfig = require_permission(Permission.MANAGE_CONFIG)

