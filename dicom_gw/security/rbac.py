"""Role-Based Access Control (RBAC) utilities."""

from typing import List, Optional, Dict
from enum import Enum

from dicom_gw.security.auth import decode_access_token


class Role(str, Enum):
    """User roles."""
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    VIEWER = "viewer"


# Role hierarchy: higher roles have all permissions of lower roles
ROLE_HIERARCHY = {
    Role.ADMIN: [Role.ADMIN, Role.OPERATOR, Role.USER, Role.VIEWER],
    Role.OPERATOR: [Role.OPERATOR, Role.USER, Role.VIEWER],
    Role.USER: [Role.USER, Role.VIEWER],
    Role.VIEWER: [Role.VIEWER],
}


# Permission definitions
class Permission(str, Enum):
    """System permissions."""
    # Studies
    VIEW_STUDIES = "studies:view"
    MANAGE_STUDIES = "studies:manage"
    FORWARD_STUDIES = "studies:forward"
    
    # Destinations
    VIEW_DESTINATIONS = "destinations:view"
    MANAGE_DESTINATIONS = "destinations:manage"
    
    # Queues
    VIEW_QUEUES = "queues:view"
    MANAGE_QUEUES = "queues:manage"
    
    # Configuration
    VIEW_CONFIG = "config:view"
    MANAGE_CONFIG = "config:manage"
    
    # Users
    VIEW_USERS = "users:view"
    MANAGE_USERS = "users:manage"
    
    # Audit
    VIEW_AUDIT = "audit:view"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.VIEW_STUDIES,
        Permission.MANAGE_STUDIES,
        Permission.FORWARD_STUDIES,
        Permission.VIEW_DESTINATIONS,
        Permission.MANAGE_DESTINATIONS,
        Permission.VIEW_QUEUES,
        Permission.MANAGE_QUEUES,
        Permission.VIEW_CONFIG,
        Permission.MANAGE_CONFIG,
        Permission.VIEW_USERS,
        Permission.MANAGE_USERS,
        Permission.VIEW_AUDIT,
    ],
    Role.OPERATOR: [
        Permission.VIEW_STUDIES,
        Permission.MANAGE_STUDIES,
        Permission.FORWARD_STUDIES,
        Permission.VIEW_DESTINATIONS,
        Permission.MANAGE_DESTINATIONS,
        Permission.VIEW_QUEUES,
        Permission.MANAGE_QUEUES,
        Permission.VIEW_CONFIG,
    ],
    Role.USER: [
        Permission.VIEW_STUDIES,
        Permission.FORWARD_STUDIES,
        Permission.VIEW_DESTINATIONS,
        Permission.VIEW_QUEUES,
    ],
    Role.VIEWER: [
        Permission.VIEW_STUDIES,
        Permission.VIEW_DESTINATIONS,
        Permission.VIEW_QUEUES,
    ],
}


def has_permission(user_role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission.
    
    Args:
        user_role: User role string
        permission: Permission to check
    
    Returns:
        True if role has permission, False otherwise
    """
    try:
        role = Role(user_role)
    except ValueError:
        return False
    
    permissions = ROLE_PERMISSIONS.get(role, [])
    return permission in permissions


def has_any_permission(user_role: str, permissions: List[Permission]) -> bool:
    """Check if a role has any of the specified permissions.
    
    Args:
        user_role: User role string
        permissions: List of permissions to check
    
    Returns:
        True if role has any permission, False otherwise
    """
    return any(has_permission(user_role, perm) for perm in permissions)


def require_role(user_role: str, required_role: Role) -> bool:
    """Check if user role meets or exceeds required role.
    
    Args:
        user_role: User role string
        required_role: Minimum required role
    
    Returns:
        True if user role meets requirement, False otherwise
    """
    try:
        role = Role(user_role)
    except ValueError:
        return False
    
    allowed_roles = ROLE_HIERARCHY.get(required_role, [])
    return role in allowed_roles


def get_current_user_from_token(token: str) -> Optional[Dict]:
    """Get current user information from JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Dictionary with user information (user_id, username, role) or None
    """
    payload = decode_access_token(token)
    if not payload:
        return None
    
    return {
        "user_id": payload.get("sub"),  # Subject (user_id)
        "username": payload.get("username"),
        "role": payload.get("role"),
    }

