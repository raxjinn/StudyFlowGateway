"""Authentication and authorization utilities."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import argon2

from dicom_gw.config.settings import get_settings

logger = logging.getLogger(__name__)

# Password hashing context using argon2id
settings = get_settings()
pwd_context = CryptContext(
    schemes=["argon2"],
    argon2__hash_len=32,
    argon2__time_cost=settings.argon2_time_cost,
    argon2__memory_cost=settings.argon2_memory_cost,
    argon2__parallelism=settings.argon2_parallelism,
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a password using argon2id.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password string
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Args:
        data: Dictionary with token payload (typically user_id, username, role)
        expires_delta: Optional expiration time delta (defaults to settings)
    
    Returns:
        Encoded JWT token string
    """
    from datetime import timezone
    
    app_settings = get_settings()
    
    if not app_settings.secret_key:
        raise ValueError("JWT secret key is not configured")
    
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=app_settings.jwt_expiration_hours)
    
    to_encode.update({"exp": expire, "iat": now})
    
    encoded_jwt = jwt.encode(
        to_encode,
        app_settings.secret_key,
        algorithm=app_settings.jwt_algorithm,
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload if valid, None otherwise
    """
    app_settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            app_settings.secret_key,
            algorithms=[app_settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        logger.debug("JWT decode error: %s", e)
        return None


def get_password_hash_argon2(password: str) -> str:
    """Hash password using argon2 directly (for compatibility).
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    app_settings = get_settings()
    
    ph = argon2.PasswordHasher(
        time_cost=app_settings.argon2_time_cost,
        memory_cost=app_settings.argon2_memory_cost,
        parallelism=app_settings.argon2_parallelism,
    )
    
    return ph.hash(password)


def verify_password_argon2(plain_password: str, hashed_password: str) -> bool:
    """Verify password using argon2 directly.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password string
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        ph = argon2.PasswordHasher()
        ph.verify(hashed_password, plain_password)
        return True
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.InvalidHash) as e:
        logger.debug("Password verification failed: %s", e)
        return False
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False

