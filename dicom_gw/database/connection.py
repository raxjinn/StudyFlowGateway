"""Database connection pooling and session management."""

import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event
from sqlalchemy.engine import Engine

from dicom_gw.config.settings import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions with async pooling."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager with connection pool.
        
        Args:
            database_url: Optional database URL override. If None, uses settings.
        """
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        
        # Create async engine with connection pooling
        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=settings.database_pool_min,
            max_overflow=settings.database_pool_max - settings.database_pool_min,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=settings.app_debug,  # Log SQL queries in debug mode
            future=True,
        )
        
        # Create session factory
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
        logger.info(
            f"Database connection pool initialized: "
            f"min={settings.database_pool_min}, max={settings.database_pool_max}"
        )
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.
        
        Yields:
            AsyncSession: Database session
        """
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close all database connections."""
        await self.engine.dispose()
        logger.info("Database connection pool closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance (singleton)."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function for FastAPI to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session


async def init_db():
    """Initialize database (create tables if not exists).
    
    Note: In production, use Alembic migrations instead.
    """
    from dicom_gw.database.models import Base
    from dicom_gw.database.encryption import get_db_encryption
    
    db_manager = get_db_manager()
    
    # Ensure pgcrypto extension is enabled
    async with db_manager.get_session() as session:
        db_encryption = get_db_encryption()
        await db_encryption.ensure_pgcrypto_extension(session)
    
    # Create tables
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


async def close_db():
    """Close database connections."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None

