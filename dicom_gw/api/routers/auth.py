"""Authentication endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import (
    hash_password,
    verify_password,
    create_access_token,
)
from dicom_gw.security.audit import log_login_attempt, log_user_action, log_audit_event
from dicom_gw.api.dependencies import RequireAdmin, get_current_user
from sqlalchemy import select
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter()

# Note: oauth2_scheme and get_current_user are now in dicom_gw.api.dependencies
# to avoid circular imports


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    email: Optional[str]
    role: str
    full_name: Optional[str]
    enabled: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Create user request model."""
    username: str
    email: Optional[EmailStr] = None
    password: str
    role: str = "user"
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    """Update user request model."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    full_name: Optional[str] = None
    enabled: Optional[bool] = None


class PasswordChange(BaseModel):
    """Password change request model."""
    current_password: str
    new_password: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Login endpoint - returns JWT token."""
    # Get client IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Store user info outside session context for audit logging
    user_id = None
    username_for_audit = form_data.username
    user_role = None
    login_success = False
    error_message = None
    
    try:
        async for session in get_db_session():
            result = await session.execute(
                select(User).where(User.username == form_data.username)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Don't reveal if user exists - break and log outside session
                error_message = "User not found"
                break
            
            # Store username for audit logging
            username_for_audit = user.username
            
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.now(timezone.utc):
                error_message = "Account locked"
                break
            
            # Check if account is disabled
            if not user.enabled:
                error_message = "Account disabled"
                break
            
            # Verify password
            if not verify_password(form_data.password, user.password_hash):
                # Increment failed login attempts
                user.failed_login_attempts += 1
                
                # Lock account after 5 failed attempts for 30 minutes
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                    logger.warning("Account locked due to failed login attempts: %s", user.username)
                
                await session.commit()
                # Break out of session context before logging
                error_message = "Incorrect password"
                break
            
            # Successful login - reset failed attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = datetime.now(timezone.utc)
            await session.commit()
            
            # Store user info for token creation and audit logging
            user_id = str(user.id)
            user_role = user.role
            login_success = True
            break
        
        # Handle error cases (outside session context)
        if error_message:
            if error_message == "User not found":
                # Log failed login attempt (outside session)
                await log_login_attempt(
                    username=form_data.username,
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=error_message,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            elif error_message == "Account locked":
                await log_login_attempt(
                    username=username_for_audit,
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=error_message,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is locked",
                )
            elif error_message == "Account disabled":
                await log_login_attempt(
                    username=username_for_audit,
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=error_message,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is disabled",
                )
            else:  # Incorrect password
                await log_login_attempt(
                    username=username_for_audit,
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=error_message,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Create access token and log audit outside session context (success case)
        if login_success:
            if not user_id or not username_for_audit or not user_role:
                logger.error("Login succeeded but user data is incomplete: user_id=%s, username=%s, role=%s", 
                           user_id, username_for_audit, user_role)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An error occurred during login",
                )
            
            from dicom_gw.config.settings import get_settings
            
            try:
                settings = get_settings()
                access_token = create_access_token(
                    data={
                        "sub": user_id,
                        "username": username_for_audit,
                        "role": user_role,
                    },
                    expires_delta=timedelta(hours=settings.jwt_expiration_hours),
                )
            except Exception as token_error:
                logger.error("Failed to create access token: %s", token_error, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An error occurred during login",
                )
            
            # Log successful login (outside session context)
            try:
                await log_login_attempt(
                    username=username_for_audit,
                    success=True,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    user_id=user_id,
                )
            except Exception as log_error:
                # Don't fail on audit logging errors, but log them
                logger.error("Failed to log successful login attempt: %s", log_error)
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.jwt_expiration_hours * 3600,
            )
        
        # If we get here without login_success or error_message, something went wrong
        logger.error("Login function reached end without success or error message")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login",
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error("Login error: %s", e, exc_info=True)
        # Use username_for_audit which is initialized to form_data.username
        try:
            await log_login_attempt(
                username=username_for_audit,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=f"Login error: {str(e)}",
            )
        except Exception as log_error:
            # Don't fail on audit logging errors
            logger.error("Failed to log login attempt: %s", log_error)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login",
        ) from None  # Don't chain exception to avoid leaking internal details


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.post("/auth/password/change")
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
):
    """Change user password."""
    async for session in get_db_session():
        # Reload user to get latest state
        result = await session.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify current password
        if not verify_password(password_change.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Update password
        user.password_hash = hash_password(password_change.new_password)
        await session.commit()
        
        return {"status": "success", "message": "Password changed successfully"}


@router.post("/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):  # pylint: disable=unused-argument
    """Logout endpoint (client should discard token)."""
    # In a stateless JWT system, logout is handled client-side
    # Optionally, we could implement a token blacklist here
    return {"status": "success", "message": "Logged out successfully"}


# User Management Endpoints (Admin only)
@router.get("/auth/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(RequireAdmin),  # noqa: ARG001
    skip: int = 0,
    limit: int = 100,
):
    """List all users (admin only)."""
    async for session in get_db_session():
        result = await session.execute(
            select(User).offset(skip).limit(limit).order_by(User.username)
        )
        users = result.scalars().all()
        return [UserResponse.model_validate(user) for user in users]


@router.post("/auth/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(RequireAdmin),
):
    """Create a new user (admin only)."""
    async for session in get_db_session():
        # Check if username already exists
        result = await session.execute(
            select(User).where(User.username == user_data.username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
        
        # Check if email already exists (if provided)
        if user_data.email:
            result = await session.execute(
                select(User).where(User.email == user_data.email)
            )
            existing_email = result.scalar_one_or_none()
            
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists",
                )
        
        # Validate role
        valid_roles = ["admin", "operator", "user", "viewer"]
        if user_data.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
            )
        
        # Create new user
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role=user_data.role,
            full_name=user_data.full_name,
            enabled=True,
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        # Log user creation
        await log_user_action(
            action="create_user",
            user_id=str(current_user.id),
            username=current_user.username,
            target_user_id=str(new_user.id),
            target_username=new_user.username,
        )
        
        return UserResponse.model_validate(new_user)


@router.get("/auth/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(RequireAdmin),  # noqa: ARG001
):
    """Get a user by ID (admin only)."""
    async for session in get_db_session():
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        return UserResponse.model_validate(user)


@router.put("/auth/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(RequireAdmin),
):
    """Update a user (admin only)."""
    async for session in get_db_session():
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Store original values for audit log
        original_values = {
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "enabled": user.enabled,
        }
        
        # Update fields if provided
        if user_data.email is not None:
            # Check if email is already taken by another user
            if user_data.email != user.email:
                email_result = await session.execute(
                    select(User).where(User.email == user_data.email)
                )
                existing_email = email_result.scalar_one_or_none()
                
                if existing_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already exists",
                    )
            user.email = user_data.email
        
        if user_data.password is not None:
            user.password_hash = hash_password(user_data.password)
            # Unlock account and reset failed attempts when password is reset
            user.locked_until = None
            user.failed_login_attempts = 0
        
        if user_data.role is not None:
            valid_roles = ["admin", "operator", "user", "viewer"]
            if user_data.role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
                )
            user.role = user_data.role
        
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        
        if user_data.enabled is not None:
            user.enabled = user_data.enabled
            # Unlock account when enabling
            if user_data.enabled:
                user.locked_until = None
                user.failed_login_attempts = 0
        
        await session.commit()
        await session.refresh(user)
        
        # Log user update
        changes = {k: v for k, v in user_data.model_dump(exclude_unset=True).items() if k != "password"}
        await log_audit_event(
            action="update_user",
            user_id=str(current_user.id),
            username=current_user.username,
            resource_type="user",
            resource_id=str(user.id),
            metadata={
                "original": original_values,
                "changes": changes,
            },
        )
        
        return UserResponse.model_validate(user)


@router.delete("/auth/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(RequireAdmin),
):
    """Delete a user (admin only)."""
    async for session in get_db_session():
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Prevent deleting yourself
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )
        
        username = user.username
        user_role = user.role
        
        # Delete user
        await session.delete(user)
        await session.commit()
        
        # Log user deletion
        await log_user_action(
            action="delete_user",
            user_id=str(current_user.id),
            username=current_user.username,
            target_user_id=str(user_id),
            target_username=username,
        )
        
        return {"status": "success", "message": f"User '{username}' deleted successfully"}

