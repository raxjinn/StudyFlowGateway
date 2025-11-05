"""Advanced PostgreSQL connection pooling with prepared statements and batch operations."""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Pool, Connection

from dicom_gw.config.settings import get_settings
from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


class AsyncPGPool:
    """High-performance async PostgreSQL connection pool with prepared statements."""
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        max_queries: int = 50000,
        max_inactive_connection_lifetime: float = 300.0,
    ):
        """Initialize asyncpg connection pool.
        
        Args:
            database_url: PostgreSQL connection URL (asyncpg format)
            min_size: Minimum pool size
            max_size: Maximum pool size
            max_queries: Maximum queries per connection before recycling
            max_inactive_connection_lifetime: Seconds before closing idle connections
        """
        settings = get_settings()
        
        # Parse database URL for asyncpg
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        if database_url:
            self.database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        else:
            self.database_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        self.min_size = min_size or settings.database_pool_min
        self.max_size = max_size or settings.database_pool_max
        self.max_queries = max_queries
        self.max_inactive_connection_lifetime = max_inactive_connection_lifetime
        self.acquire_timeout = settings.database_pool_acquire_timeout
        
        self.pool: Optional[Pool] = None
        self._prepared_statements: Dict[str, asyncpg.PreparedStatement] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Create and initialize the connection pool."""
        if self.pool is not None:
            return
        
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            max_queries=self.max_queries,
            max_inactive_connection_lifetime=self.max_inactive_connection_lifetime,
            command_timeout=self.acquire_timeout,
            server_settings={
                "application_name": "dicom_gateway",
                "statement_cache_size": "500",  # Enable prepared statement caching
            },
        )
        logger.info(
            f"AsyncPG connection pool initialized: "
            f"min={self.min_size}, max={self.max_size}"
        )
        
        # Update metrics
        metrics = get_metrics_collector()
        metrics.update_db_pool(
            active=0,
            idle=self.min_size,
            waiting=0,
            min_size=self.min_size,
            max_size=self.max_size,
            current=self.min_size,
        )
    
    async def close(self):
        """Close the connection pool and all connections."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._prepared_statements.clear()
            logger.info("AsyncPG connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool.
        
        Yields:
            Connection: Database connection
        """
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query and return the command status.
        
        Args:
            query: SQL query string
            *args: Query parameters
        
        Returns:
            Command status string (e.g., "INSERT 1")
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Execute a query and fetch all results.
        
        Args:
            query: SQL query string
            *args: Query parameters
        
        Returns:
            List of records
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Execute a query and fetch one row.
        
        Args:
            query: SQL query string
            *args: Query parameters
        
        Returns:
            Single record or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """Execute a query and fetch a single value.
        
        Args:
            query: SQL query string
            *args: Query parameters
        
        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def copy_records_to_table(
        self,
        table_name: str,
        records: List[tuple],
        columns: Optional[List[str]] = None,
    ) -> None:
        """Bulk insert records using PostgreSQL COPY.
        
        This is the fastest way to insert large batches of data.
        
        Args:
            table_name: Target table name
            records: List of tuples containing row data
            columns: Optional list of column names
        """
        async with self.acquire() as conn:
            await conn.copy_records_to_table(
                table_name,
                records=records,
                columns=columns,
            )
    
    async def prepare_statement(self, name: str, query: str) -> asyncpg.PreparedStatement:
        """Prepare a statement for reuse (server-side prepared statement).
        
        Args:
            name: Unique name for the prepared statement
            query: SQL query string
        
        Returns:
            Prepared statement object
        """
        async with self._lock:
            if name in self._prepared_statements:
                return self._prepared_statements[name]
            
            async with self.acquire() as conn:
                stmt = await conn.prepare(query)
                self._prepared_statements[name] = stmt
                logger.debug(f"Prepared statement cached: {name}")
                return stmt
    
    async def execute_prepared(self, name: str, *args) -> Any:
        """Execute a prepared statement.
        
        Args:
            name: Name of the prepared statement
            *args: Query parameters
        
        Returns:
            Query result
        """
        if name not in self._prepared_statements:
            raise ValueError(f"Prepared statement '{name}' not found")
        
        stmt = self._prepared_statements[name]
        async with self.acquire() as conn:
            # Reuse the prepared statement on this connection
            # Note: asyncpg handles statement caching per connection
            return await conn.fetch(stmt.query, *args)
    
    @asynccontextmanager
    async def transaction(self):
        """Start a transaction.
        
        Yields:
            Connection: Database connection in transaction context
        """
        async with self.acquire() as conn:
            async with conn.transaction() as tx:
                yield tx


# Global pool instance
_asyncpg_pool: Optional[AsyncPGPool] = None


def get_asyncpg_pool() -> AsyncPGPool:
    """Get the global asyncpg pool instance (singleton)."""
    global _asyncpg_pool
    if _asyncpg_pool is None:
        _asyncpg_pool = AsyncPGPool()
    return _asyncpg_pool


async def init_asyncpg_pool():
    """Initialize the global asyncpg pool."""
    pool = get_asyncpg_pool()
    await pool.initialize()


async def close_asyncpg_pool():
    """Close the global asyncpg pool."""
    global _asyncpg_pool
    if _asyncpg_pool:
        await _asyncpg_pool.close()
        _asyncpg_pool = None

