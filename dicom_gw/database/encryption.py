"""Database encryption utilities using pgcrypto."""

import logging
import os
from typing import Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseEncryption:
    """Database encryption utility using PostgreSQL pgcrypto extension."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize database encryption.
        
        Args:
            encryption_key: Encryption key (defaults to DICOM_GW_DB_ENCRYPTION_KEY env var)
        """
        self.encryption_key = encryption_key or os.getenv("DICOM_GW_DB_ENCRYPTION_KEY", "")
        
        if not self.encryption_key:
            logger.warning(
                "No encryption key provided. Database encryption will not work. "
                "Set DICOM_GW_DB_ENCRYPTION_KEY environment variable."
            )
    
    async def ensure_pgcrypto_extension(self, session) -> bool:
        """Ensure pgcrypto extension is enabled in the database.
        
        Args:
            session: SQLAlchemy async session
        
        Returns:
            True if extension is enabled, False otherwise
        """
        try:
            await session.execute(
                text("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            )
            await session.commit()
            logger.info("pgcrypto extension enabled")
            return True
        except Exception as e:
            logger.error("Failed to enable pgcrypto extension: %s", e, exc_info=True)
            await session.rollback()
            return False
    
    async def encrypt_value(self, session, value: str) -> Optional[str]:
        """Encrypt a value using pgcrypto.
        
        Args:
            session: SQLAlchemy async session
            value: Value to encrypt
        
        Returns:
            Encrypted value (hex-encoded) or None if encryption fails
        """
        if not self.encryption_key:
            logger.warning("Cannot encrypt: no encryption key provided")
            return None
        
        if not value:
            return None
        
        try:
            result = await session.execute(
                text("SELECT pgp_sym_encrypt(:value, :key) as encrypted"),
                {"value": value, "key": self.encryption_key}
            )
            row = result.fetchone()
            if row:
                # pgp_sym_encrypt returns bytea, convert to hex string
                encrypted_hex = row[0]
                return encrypted_hex
            return None
        except Exception as e:
            logger.error("Failed to encrypt value: %s", e, exc_info=True)
            return None
    
    async def decrypt_value(self, session, encrypted_value: str) -> Optional[str]:
        """Decrypt a value using pgcrypto.
        
        Args:
            session: SQLAlchemy async session
            encrypted_value: Encrypted value (hex-encoded)
        
        Returns:
            Decrypted value or None if decryption fails
        """
        if not self.encryption_key:
            logger.warning("Cannot decrypt: no encryption key provided")
            return None
        
        if not encrypted_value:
            return None
        
        try:
            result = await session.execute(
                text("SELECT pgp_sym_decrypt(:encrypted::bytea, :key) as decrypted"),
                {"encrypted": encrypted_value, "key": self.encryption_key}
            )
            row = result.fetchone()
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error("Failed to decrypt value: %s", e, exc_info=True)
            return None
    
    def encrypt_value_sync(self, value: str) -> Optional[str]:
        """Synchronously encrypt a value (for use outside async context).
        
        Note: This requires a database connection. For async operations, use encrypt_value().
        
        Args:
            value: Value to encrypt
        
        Returns:
            Encryption SQL expression string or None
        """
        if not self.encryption_key:
            logger.warning("Cannot encrypt: no encryption key provided")
            return None
        
        if not value:
            return None
        
        # Return SQL expression for use in queries
        return f"pgp_sym_encrypt('{value.replace("'", "''")}', '{self.encryption_key.replace("'", "''")}')"
    
    def decrypt_value_sync(self, column_name: str) -> str:
        """Synchronously decrypt a column (for use in SQL queries).
        
        Args:
            column_name: Name of the encrypted column
        
        Returns:
            Decryption SQL expression string
        """
        if not self.encryption_key:
            logger.warning("Cannot decrypt: no encryption key provided")
            return column_name
        
        # Return SQL expression for use in queries
        return f"pgp_sym_decrypt({column_name}::bytea, '{self.encryption_key.replace("'", "''")}')"


# Global encryption instance
_db_encryption: Optional[DatabaseEncryption] = None


def get_db_encryption() -> DatabaseEncryption:
    """Get the global database encryption instance.
    
    Returns:
        DatabaseEncryption instance
    """
    global _db_encryption  # noqa: PLW0603
    if _db_encryption is None:
        _db_encryption = DatabaseEncryption()
    return _db_encryption

