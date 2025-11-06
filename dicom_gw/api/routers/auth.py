"""Authentication endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import (
    hash_password,
    verify_password,
    create_access_token,
)
from dicom_gw.security.audit import log_login_attempt
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


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


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency to get current authenticated user.
    
    Args:
        token: JWT token from request
    
    Returns:
        User database object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    from dicom_gw.security.auth import decode_access_token
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
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


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Login endpoint - returns JWT token."""
    # Get client IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    async for session in get_db_session():
        result = await session.execute(
            select(User).where(User.username == form_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal if user exists
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is locked",
            )
        
        # Check if account is disabled
        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        
        # Verify password
        if not verify_password(form_data.password, user.password_hash):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts for 30 minutes
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                logger.warning("Account locked due to failed login attempts: %s", user.username)
            
            await session.commit()
            
            # Log failed login attempt
            await log_login_attempt(
                username=form_data.username,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Incorrect password",
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Successful login - reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()
        
        # Create access token
        from dicom_gw.config.settings import get_settings
        
        settings = get_settings()
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
            },
            expires_delta=timedelta(hours=settings.jwt_expiration_hours),
        )
        
        # Log successful login
        await log_login_attempt(
            username=user.username,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
            user_id=str(user.id),
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expiration_hours * 3600,
        )


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

