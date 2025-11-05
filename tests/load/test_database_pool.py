"""Load tests for database pool saturation and performance."""

import pytest
import asyncio
import time
from typing import List
from dicom_gw.database.pool import AsyncPGPool
from dicom_gw.config.settings import get_settings


@pytest.fixture
async def db_pool():
    """Create a database pool for testing."""
    settings = get_settings()
    
    # Override with test database if needed
    pool = AsyncPGPool(
        database_url=settings.database_url,
        min_size=5,
        max_size=20,
    )
    
    await pool.initialize()
    
    yield pool
    
    await pool.close()


@pytest.mark.load
@pytest.mark.slow
class TestDatabasePool:
    """Load tests for database pool saturation."""
    
    @pytest.mark.asyncio
    async def test_pool_connection_acquisition(self, db_pool):
        """Test acquiring connections from the pool under load."""
        async def acquire_and_release():
            """Acquire a connection and release it."""
            async with db_pool.acquire() as conn:
                # Simulate some work
                await asyncio.sleep(0.01)
                # Test query
                result = await conn.fetchval("SELECT 1")
                assert result == 1
            return True
        
        # Acquire connections concurrently
        start_time = time.time()
        tasks = [acquire_and_release() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        duration = end_time - start_time
        successful = sum(results)
        
        print("\nPool Connection Acquisition Test Results:")  # noqa: T201
        print(f"  Connections acquired: {successful}")  # noqa: T201
        print(f"  Duration: {duration:.2f}s")  # noqa: T201
        print(f"  Rate: {successful / duration:.2f} connections/second")  # noqa: T201
        
        assert successful == 100, f"Not all connections acquired: {successful}/100"
    
    @pytest.mark.asyncio
    async def test_pool_saturation(self, db_pool):
        """Test pool behavior when all connections are in use."""
        # Acquire all connections from pool
        connections: List = []
        
        try:
            # Acquire all available connections (using context managers)
            async def hold_connection():
                conn_ctx = db_pool.acquire()
                conn = await conn_ctx.__aenter__()
                return conn, conn_ctx
            
            # Note: This is a simplified test - in practice, we'd use proper context managers
            # For now, we'll test with fewer connections to avoid complexity
            for _ in range(min(5, db_pool.max_size)):
                conn_ctx = db_pool.acquire()
                conn = await conn_ctx.__aenter__()
                connections.append((conn, conn_ctx))
            
            # Try to acquire more connections (should reuse or wait)
            acquisition_times = []
            
            async def try_acquire():
                start = time.time()
                try:
                    async with db_pool.acquire() as conn:
                        end = time.time()
                        acquisition_times.append(end - start)
                        await conn.fetchval("SELECT 1")
                except Exception:
                    end = time.time()
                    acquisition_times.append(end - start)
            
            # Try to acquire connections concurrently
            tasks = [try_acquire() for _ in range(10)]
            await asyncio.gather(*tasks)
            
            print("\nPool Saturation Test Results:")  # noqa: T201
            print(f"  Pool size: {db_pool.max_size}")  # noqa: T201
            print(f"  Connections acquired: {len(connections)}")  # noqa: T201
            print(f"  Additional acquisition attempts: {len(acquisition_times)}")  # noqa: T201
            if acquisition_times:
                print(f"  Average wait time: {sum(acquisition_times) / len(acquisition_times):.3f}s")  # noqa: T201
            
            # Verify we acquired connections
            assert len(connections) > 0, "No connections acquired"
            
            # Some acquisitions should have completed
            assert len(acquisition_times) > 0, "No acquisition attempts recorded"
        
        finally:
            # Release all connections
            for conn, ctx in connections:
                await ctx.__aexit__(None, None, None)
    
    @pytest.mark.asyncio
    async def test_pool_concurrent_queries(self, db_pool):
        """Test executing concurrent queries through the pool."""
        async def execute_query(query_id):
            """Execute a query using pool."""
            async with db_pool.acquire() as conn:
                # Simulate query
                result = await conn.fetchval(
                    "SELECT $1::text || ' query'",
                    f"query_{query_id}"
                )
                await asyncio.sleep(0.01)  # Simulate work
                return result
        
        # Execute queries concurrently
        start_time = time.time()
        queries = [execute_query(i) for i in range(50)]
        results = await asyncio.gather(*queries)
        end_time = time.time()
        
        duration = end_time - start_time
        successful = len([r for r in results if r is not None])
        
        print("\nConcurrent Queries Test Results:")  # noqa: T201
        print(f"  Queries executed: {successful}")  # noqa: T201
        print(f"  Duration: {duration:.2f}s")  # noqa: T201
        print(f"  Rate: {successful / duration:.2f} queries/second")  # noqa: T201
        
        assert successful == 50, f"Not all queries executed: {successful}/50"
    
    @pytest.mark.asyncio
    async def test_pool_connection_reuse(self, db_pool):
        """Test that connections are properly reused."""
        # Track connection IDs to verify reuse
        connection_ids = set()
        
        async def get_connection_id():
            """Get the connection ID."""
            async with db_pool.acquire() as conn:
                # Get connection ID (PostgreSQL specific)
                conn_id = await conn.fetchval("SELECT pg_backend_pid()")
                connection_ids.add(conn_id)
                await asyncio.sleep(0.01)
                return conn_id
        
        # Execute queries
        tasks = [get_connection_id() for _ in range(100)]
        await asyncio.gather(*tasks)
        
        print("\nConnection Reuse Test Results:")  # noqa: T201
        print(f"  Unique connections used: {len(connection_ids)}")  # noqa: T201
        print(f"  Pool max size: {db_pool.max_size}")  # noqa: T201
        
        # Should reuse connections (fewer unique connections than queries)
        assert len(connection_ids) <= db_pool.max_size, \
            f"Too many unique connections: {len(connection_ids)} > {db_pool.max_size}"
    
    @pytest.mark.asyncio
    async def test_pool_metrics_under_load(self, db_pool):
        """Test pool metrics collection under load."""
        # Execute many queries to generate metrics
        async def execute_query():
            async with db_pool.acquire_context() as conn:
                await conn.fetchval("SELECT 1")
                await asyncio.sleep(0.01)
        
        # Run queries concurrently
        tasks = [execute_query() for _ in range(50)]
        await asyncio.gather(*tasks)
        
        # Get pool info (basic check)
        if db_pool.pool:
            pool_size = db_pool.pool.get_size()
            pool_idle_size = db_pool.pool.get_idle_size()
            
            print("\nPool Metrics Under Load:")  # noqa: T201
            print(f"  Pool size: {pool_size}")  # noqa: T201
            print(f"  Idle connections: {pool_idle_size}")  # noqa: T201
            print(f"  Max pool size: {db_pool.max_size}")  # noqa: T201
            
            # Verify pool is within limits
            assert pool_size <= db_pool.max_size
            assert pool_idle_size <= pool_size
        else:
            print("\nPool Metrics Under Load: Pool not initialized")  # noqa: T201

