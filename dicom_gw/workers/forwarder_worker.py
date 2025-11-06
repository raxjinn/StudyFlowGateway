"""Forwarding Worker Service.

This worker processes ForwardJob entries from the database and forwards
studies to configured DICOM Application Entities with retry logic.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dicom_gw.dicom.forwarder import Forwarder, ForwardResult
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import ForwardJob, Study, Destination
from dicom_gw.config.settings import get_settings
from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


class ForwarderWorker:
    """Worker that processes ForwardJob entries and forwards studies to remote AEs."""
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: float = 5.0,
        batch_size: int = 5,
    ):
        """Initialize forwarding worker.
        
        Args:
            worker_id: Optional worker identifier
            poll_interval: Seconds between polls when no jobs available
            batch_size: Maximum jobs to process in one batch
        """
        # Generate worker ID - use time.time() instead of asyncio.get_event_loop().time()
        import time
        self.worker_id = worker_id or f"forwarder-worker-{time.time()}"
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.forwarder = Forwarder()
        self.running = False
        self.stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "started_at": None,
        }
        
        settings = get_settings()
        self.storage_path = Path(settings.dicom_incoming_path)
        
        logger.info("ForwarderWorker initialized: %s", self.worker_id)
    
    async def start(self):
        """Start the forwarding worker."""
        self.running = True
        self.stats["started_at"] = datetime.now(timezone.utc)
        
        logger.info("Starting forwarding worker: %s", self.worker_id)
        
        # Main processing loop
        while self.running:
            try:
                await self._process_forward_jobs()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in forwarding worker main loop: %s", e, exc_info=True)
                await asyncio.sleep(self.poll_interval)
    
    async def stop(self):
        """Stop the forwarding worker."""
        logger.info("Stopping forwarding worker: %s", self.worker_id)
        self.running = False
    
    async def _process_forward_jobs(self):
        """Process available ForwardJob entries."""
        try:
            # Get pending forward jobs
            jobs = await self._get_pending_jobs()
            
            if not jobs:
                return  # No jobs available
            
            logger.debug("Processing %d forward job(s)", len(jobs))
            
            # Process each job
            for job in jobs:
                await self._process_forward_job(job)
        
        except Exception as e:
            logger.error("Error processing forward jobs: %s", e, exc_info=True)
    
    async def _get_pending_jobs(self) -> list[ForwardJob]:
        """Get pending forward jobs from database.
        
        Uses SKIP LOCKED to allow concurrent workers.
        
        Returns:
            List of ForwardJob objects
        """
        jobs = []
        
        async for session in get_db_session():
            # Get pending jobs that are available now
            result = await session.execute(
                select(ForwardJob)
                .where(ForwardJob.status == "pending")
                .where(ForwardJob.available_at <= datetime.now(timezone.utc))
                .where(ForwardJob.destination.has(Destination.enabled == True))  # noqa: E712
                .order_by(ForwardJob.priority.desc(), ForwardJob.created_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            
            job_list = result.scalars().all()
            
            if job_list:
                # Update jobs to "processing" status
                job_ids = [job.id for job in job_list]
                await session.execute(
                    update(ForwardJob)
                    .where(ForwardJob.id.in_(job_ids))
                    .values(
                        status="processing",
                        started_at=datetime.now(timezone.utc),
                        attempts=ForwardJob.attempts + 1,
                    )
                )
                await session.commit()
                
                # Reload jobs to get updated attempts count
                result = await session.execute(
                    select(ForwardJob).where(ForwardJob.id.in_(job_ids))
                )
                jobs = result.scalars().all()
            
            break
        
        return jobs
    
    async def _process_forward_job(self, job: ForwardJob):
        """Process a single forward job.
        
        Args:
            job: ForwardJob database object
        """
        try:
            logger.debug(
                "Processing forward job: %s (study: %s, destination: %s, attempt: %d/%d)",
                str(job.id),
                job.study.study_instance_uid[:40] if job.study else "unknown",
                job.destination.name if job.destination else "unknown",
                job.attempts,
                job.max_attempts,
            )
            
            # Forward the study
            result = await self.forwarder.forward_job(job, self.storage_path)
            
            # Update job status based on result
            async for session in get_db_session():
                # Reload job to get latest state
                result_obj = await session.execute(
                    select(ForwardJob).where(ForwardJob.id == job.id)
                )
                current_job = result_obj.scalar_one_or_none()
                
                if not current_job:
                    logger.warning("ForwardJob not found: %s", str(job.id))
                    break
                
                if result.success:
                    # Success
                    current_job.status = "completed"
                    current_job.completed_at = datetime.now(timezone.utc)
                    current_job.error_message = None
                    current_job.duration_ms = result.duration_ms
                    
                    if result.stats:
                        current_job.instances_sent = result.stats.get("instances_forwarded", 0)
                        current_job.instances_failed = result.stats.get("instances_failed", 0)
                    
                    # Update study status
                    if current_job.study:
                        current_job.study.status = "forwarded"
                        current_job.study.forwarded_at = datetime.now(timezone.utc)
                    
                    # Update destination stats
                    destination_name = "unknown"
                    if current_job.destination:
                        current_job.destination.last_success_at = datetime.now(timezone.utc)
                        current_job.destination.consecutive_failures = 0
                        destination_name = current_job.destination.name
                    
                    # Record metrics
                    metrics = get_metrics_collector()
                    metrics.record_forward(
                        destination=destination_name,
                        status="success",
                        duration_seconds=result.duration_ms / 1000.0 if result.duration_ms else 0,
                    )
                    
                    await session.commit()
                    
                    self.stats["processed"] += 1
                    self.stats["succeeded"] += 1
                    
                    logger.info(
                        "Forward job completed: %s -> %s (%d instances)",
                        current_job.study.study_instance_uid[:40] if current_job.study else "unknown",
                        destination_name,
                        current_job.instances_sent,
                    )
                
                else:
                    # Failure
                    should_retry = current_job.attempts < current_job.max_attempts
                    
                    if should_retry:
                        # Calculate retry delay (exponential backoff)
                        backoff_seconds = 2 ** (current_job.attempts - 1)  # 1, 2, 4, 8, ...
                        current_job.status = "pending"
                        current_job.available_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                        current_job.retry_after = current_job.available_at
                        current_job.error_message = result.error_message
                        
                        logger.warning(
                            "Forward job failed, will retry: %s (attempt %d/%d, retry in %ds)",
                            str(current_job.id),
                            current_job.attempts,
                            current_job.max_attempts,
                            backoff_seconds,
                        )
                    else:
                        # Move to dead letter queue
                        current_job.status = "dead_letter"
                        current_job.completed_at = datetime.now(timezone.utc)
                        current_job.error_message = result.error_message
                        
                        # Update destination stats
                        destination_name = "unknown"
                        if current_job.destination:
                            current_job.destination.last_failure_at = datetime.now(timezone.utc)
                            current_job.destination.consecutive_failures += 1
                            destination_name = current_job.destination.name
                        
                        # Record metrics
                        metrics = get_metrics_collector()
                        metrics.record_forward(
                            destination=destination_name,
                            status="failed",
                            duration_seconds=result.duration_ms / 1000.0 if result.duration_ms else 0,
                        )
                        
                        logger.error(
                            "Forward job moved to dead letter: %s (failed after %d attempts)",
                            str(current_job.id),
                            current_job.attempts,
                        )
                    
                    await session.commit()
                    
                    self.stats["processed"] += 1
                    self.stats["failed"] += 1
                
                break
        
        except Exception as e:
            error_msg = str(e)
            logger.error("Exception processing forward job %s: %s", str(job.id), error_msg, exc_info=True)
            
            # Mark job as failed
            async for session in get_db_session():
                result_obj = await session.execute(
                    select(ForwardJob).where(ForwardJob.id == job.id)
                )
                current_job = result_obj.scalar_one_or_none()
                
                if current_job:
                    should_retry = current_job.attempts < current_job.max_attempts
                    
                    if should_retry:
                        backoff_seconds = 2 ** (current_job.attempts - 1)
                        current_job.status = "pending"
                        current_job.available_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                        current_job.error_message = error_msg
                    else:
                        current_job.status = "dead_letter"
                        current_job.completed_at = datetime.utcnow()
                        current_job.error_message = error_msg
                    
                    await session.commit()
                
                break
            
            self.stats["processed"] += 1
            self.stats["failed"] += 1
    
    async def cleanup_stale_jobs(self, timeout_minutes: int = 60):
        """Clean up forward jobs stuck in processing state.
        
        Args:
            timeout_minutes: Minutes after which a processing job is considered stale
        """
        timeout = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        
        async for session in get_db_session():
            result = await session.execute(
                update(ForwardJob)
                .where(ForwardJob.status == "processing")
                .where(ForwardJob.started_at < timeout)
                .values(
                    status="pending",
                    started_at=None,
                )
            )
            
            count = result.rowcount
            if count > 0:
                await session.commit()
                logger.info("Cleaned up %d stale forward job(s)", count)
            break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.
        
        Returns:
            Dictionary with statistics
        """
        uptime_seconds = 0
        if self.stats["started_at"]:
            uptime_seconds = (datetime.now(timezone.utc) - self.stats["started_at"]).total_seconds()
        
        # Update metrics
        metrics = get_metrics_collector()
        metrics.update_worker_uptime("forwarder", self.worker_id, uptime_seconds)
        
        return {
            **self.stats,
            "uptime_seconds": uptime_seconds,
            "worker_id": self.worker_id,
        }


def main():
    """Main entry point for the forwarding worker service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create worker
    worker = ForwarderWorker()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        asyncio.create_task(worker.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run worker
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        asyncio.run(worker.stop())


if __name__ == "__main__":
    main()

