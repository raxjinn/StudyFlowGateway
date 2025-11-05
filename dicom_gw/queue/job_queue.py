"""Job queue implementation with PostgreSQL backend.

This module implements a PostgreSQL-backed job queue using SKIP LOCKED pattern
for concurrent workers and LISTEN/NOTIFY for real-time notifications.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession

from dicom_gw.database.models import Job
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.pool import get_asyncpg_pool
from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result of a dequeued job."""
    job_id: str
    job_type: str
    payload: Dict[str, Any]
    attempts: int
    max_attempts: int


class JobQueue:
    """PostgreSQL-backed job queue with SKIP LOCKED and LISTEN/NOTIFY."""
    
    def __init__(self, worker_id: Optional[str] = None):
        """Initialize job queue.
        
        Args:
            worker_id: Optional worker identifier for tracking which worker processes jobs
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._listeners: Dict[str, asyncio.Task] = {}
        self._running = False
        logger.info("JobQueue initialized with worker_id: %s", self.worker_id)
    
    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: int = 0,
        max_attempts: int = 3,
        available_at: Optional[datetime] = None,
    ) -> str:
        """Enqueue a job for processing.
        
        Args:
            job_type: Type of job (e.g., "process_received_file")
            payload: Job data dictionary
            priority: Job priority (higher = more important, default: 0)
            max_attempts: Maximum retry attempts (default: 3)
            available_at: When job becomes available (default: now)
        
        Returns:
            Job ID (UUID string)
        """
        if available_at is None:
            available_at = datetime.utcnow()
        
        job_id = uuid.uuid4()
        
        async for session in get_db_session():
            job = Job(
                id=job_id,
                job_type=job_type,
                payload=payload,
                priority=priority,
                max_attempts=max_attempts,
                available_at=available_at,
                status="pending",
            )
            session.add(job)
            await session.commit()
            break
        
        # Notify listeners that a new job is available
        await self._notify_job_available(job_type)
        
        logger.debug(
            "Enqueued job: id=%s, type=%s, priority=%d",
            str(job_id),
            job_type,
            priority,
        )
        
        return str(job_id)
    
    async def dequeue(
        self,
        job_type: Optional[str] = None,
        batch_size: int = 1,
        timeout: Optional[int] = None,  # pylint: disable=unused-argument
    ) -> List[JobResult]:
        """Dequeue one or more jobs for processing.
        
        Uses SELECT FOR UPDATE SKIP LOCKED to ensure concurrent workers
        don't process the same job.
        
        Args:
            job_type: Optional job type filter (None = any type)
            batch_size: Maximum number of jobs to dequeue (default: 1)
            timeout: Optional timeout in seconds for waiting for jobs
        
        Returns:
            List of JobResult objects
        """
        jobs = []
        
        async for session in get_db_session():
            # Build query with SKIP LOCKED
            query = (
                select(Job)
                .where(Job.status == "pending")
                .where(Job.available_at <= datetime.utcnow())
                .order_by(Job.priority.desc(), Job.created_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            
            if job_type:
                query = query.where(Job.job_type == job_type)
            
            result = await session.execute(query)
            job_rows = result.scalars().all()
            
            if not job_rows:
                break
            
            # Update jobs to "processing" status
            job_ids = [job.id for job in job_rows]
            now = datetime.utcnow()
            
            await session.execute(
                update(Job)
                .where(Job.id.in_(job_ids))
                .values(
                    status="processing",
                    started_at=now,
                    locked_at=now,
                    worker_id=self.worker_id,
                    attempts=Job.attempts + 1,
                )
            )
            await session.commit()
            
            # Convert to JobResult objects
            for job in job_rows:
                jobs.append(
                    JobResult(
                        job_id=str(job.id),
                        job_type=job.job_type,
                        payload=job.payload,
                        attempts=job.attempts + 1,
                        max_attempts=job.max_attempts,
                    )
                )
            
            logger.debug(
                "Dequeued %d job(s): %s",
                len(jobs),
                ", ".join([j.job_id for j in jobs]),
            )
            break
        
        return jobs
    
    async def complete(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a job as completed.
        
        Args:
            job_id: Job ID
            result: Optional result data
        
        Returns:
            True if job was found and updated, False otherwise
        """
        async for session in get_db_session():
            job_uuid = uuid.UUID(job_id)
            result_obj = await session.execute(
                select(Job).where(Job.id == job_uuid)
            )
            job = result_obj.scalar_one_or_none()
            
            if not job:
                logger.warning("Job not found for completion: %s", job_id)
                return False
            
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result = result
            
            # Record metrics
            metrics = get_metrics_collector()
            metrics.record_queue_job(job_type=job.job_type, status="completed")
            
            await session.commit()
            logger.debug("Completed job: %s", job_id)
            break
        
        return True
    
    async def fail(
        self,
        job_id: str,
        error_message: str,
        retry: bool = True,
    ) -> bool:
        """Mark a job as failed.
        
        Args:
            job_id: Job ID
            error_message: Error message
            retry: If True and attempts < max_attempts, reschedule for retry
        
        Returns:
            True if job was found and updated, False otherwise
        """
        async for session in get_db_session():
            job_uuid = uuid.UUID(job_id)
            result_obj = await session.execute(
                select(Job).where(Job.id == job_uuid)
            )
            job = result_obj.scalar_one_or_none()
            
            if not job:
                logger.warning("Job not found for failure: %s", job_id)
                return False
            
            job.error_message = error_message
            job.locked_at = None
            job.worker_id = None
            
            if retry and job.attempts < job.max_attempts:
                # Reschedule with exponential backoff
                backoff_seconds = 2 ** (job.attempts - 1)  # 1, 2, 4, 8, ...
                job.available_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
                job.status = "pending"
                job.retry_after = job.available_at
                
                logger.debug(
                    "Rescheduled job %s for retry (attempt %d/%d) in %d seconds",
                    job_id,
                    job.attempts,
                    job.max_attempts,
                    backoff_seconds,
                )
            else:
                # Move to dead letter queue
                job.status = "dead_letter"
                job.completed_at = datetime.utcnow()
                
                # Record metrics
                metrics = get_metrics_collector()
                metrics.record_queue_job(job_type=job.job_type, status="failed")
                
                logger.warning(
                    "Job %s moved to dead letter queue after %d attempts",
                    job_id,
                    job.attempts,
                )
            
            await session.commit()
            
            # Notify if rescheduled
            if job.status == "pending":
                await self._notify_job_available(job.job_type)
            
            break
        
        return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        stats = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "dead_letter": 0,
        }
        
        async for session in get_db_session():
            for status_val in stats.keys():
                result = await session.execute(
                    select(Job).where(Job.status == status_val)
                )
                stats[status_val] = len(result.scalars().all())
            break
        
        # Update Prometheus metrics
        metrics = get_metrics_collector()
        metrics.update_queue_depth("all", stats["pending"])
        metrics.update_processing_jobs("all", stats["processing"])
        
        return stats
    
    async def listen(
        self,
        job_type: Optional[str] = None,
        callback: Optional[Callable] = None,
    ) -> asyncio.Task:
        """Start listening for job availability notifications.
        
        Uses PostgreSQL LISTEN/NOTIFY to wake up workers when new jobs arrive.
        Falls back to polling if LISTEN/NOTIFY fails.
        
        Args:
            job_type: Optional job type to listen for (None = all types)
            callback: Optional callback function to call when jobs become available
        
        Returns:
            asyncio.Task for the listener
        """
        channel = f"job_queue_{job_type or 'all'}"
        
        if channel in self._listeners:
            return self._listeners[channel]
        
        async def _listener():
            pool = get_asyncpg_pool()
            await pool.initialize()
            
            try:
                async with pool.acquire() as conn:
                    # Listen on the channel
                    await conn.execute(text(f"LISTEN {channel}"))
                    logger.info("Listening for job notifications on channel: %s", channel)
                    
                    # Set up notification handler
                    def notification_handler(conn, pid, channel_name, payload):
                        logger.debug("Received notification on channel: %s", channel_name)
                        if callback:
                            # Schedule callback in event loop
                            asyncio.create_task(callback())
                    
                    conn.add_listener(channel, notification_handler)
                    
                    # Poll periodically in case notifications are missed
                    while self._running:
                        try:
                            await asyncio.wait_for(asyncio.sleep(5.0), timeout=None)
                            # Periodic check even without notification
                            if callback:
                                await callback()
                        except asyncio.CancelledError:
                            break
                        
            except Exception as e:
                logger.error("Error in job listener: %s", e, exc_info=True)
                # Fall back to polling
                await self._poll_fallback(callback)
        
        task = asyncio.create_task(_listener())
        self._listeners[channel] = task
        self._running = True
        
        return task
    
    async def _poll_fallback(self, callback: Optional[Callable] = None):
        """Fallback polling mechanism if LISTEN/NOTIFY fails."""
        logger.info("Using polling fallback for job queue")
        
        while self._running:
            try:
                if callback:
                    await callback()
                await asyncio.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error("Error in polling fallback: %s", e, exc_info=True)
                await asyncio.sleep(5)
    
    async def _notify_job_available(self, job_type: str):
        """Send NOTIFY when a new job is available.
        
        Args:
            job_type: Type of job that became available
        """
        try:
            pool = get_asyncpg_pool()
            await pool.initialize()
            
            # Notify on both specific and general channels
            channels = [
                f"job_queue_{job_type}",
                "job_queue_all",
            ]
            
            async with pool.acquire() as conn:
                for channel in channels:
                    # Use NOTIFY command
                    await conn.execute(
                        text(f"NOTIFY {channel}, 'job_available'")
                    )
            
            logger.debug("Sent job availability notification for type: %s", job_type)
        
        except Exception as e:
            logger.warning("Failed to send job notification: %s", e)
            # Non-critical, continue anyway
    
    async def stop_listening(self):
        """Stop all listeners."""
        self._running = False
        for channel, task in self._listeners.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._listeners.clear()
        logger.info("Stopped all job queue listeners")
    
    async def cleanup_stale_jobs(self, timeout_minutes: int = 30):
        """Clean up jobs that have been in processing state for too long.
        
        This handles cases where a worker crashed while processing a job.
        
        Args:
            timeout_minutes: Minutes after which a processing job is considered stale
        """
        timeout = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        async for session in get_db_session():
            result = await session.execute(
                update(Job)
                .where(Job.status == "processing")
                .where(Job.locked_at < timeout)
                .values(
                    status="pending",
                    locked_at=None,
                    worker_id=None,
                )
            )
            
            count = result.rowcount
            if count > 0:
                await session.commit()
                logger.info("Cleaned up %d stale job(s)", count)
            break
