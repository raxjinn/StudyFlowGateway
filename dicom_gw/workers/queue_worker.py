"""Queue Worker Service.

This worker processes jobs from the job queue and orchestrates tasks such as:
- Processing received DICOM files (metadata extraction)
- Triggering forwarding jobs
- Coordinating other async operations
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from dicom_gw.queue.job_queue import JobQueue, JobResult
from dicom_gw.dicom.io import parse_dicom_metadata, get_dicom_tags
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import Study, Series, Instance, IngestEvent
from dicom_gw.config.settings import get_settings
from dicom_gw.metrics.collector import get_metrics_collector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class QueueWorker:
    """Worker that processes jobs from the job queue."""
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: float = 5.0,
        batch_size: int = 10,
    ):
        """Initialize queue worker.
        
        Args:
            worker_id: Optional worker identifier
            poll_interval: Seconds between queue polls when no jobs available
            batch_size: Maximum jobs to process in one batch
        """
        # Generate worker ID - use time.time() instead of asyncio.get_event_loop().time()
        import time
        self.worker_id = worker_id or f"queue-worker-{time.time()}"
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.queue = JobQueue(worker_id=self.worker_id)
        self.running = False
        self.stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "started_at": None,
        }
        
        # Register job handlers
        self.handlers = {
            "process_received_file": self._handle_process_received_file,
            "extract_metadata": self._handle_extract_metadata,
            "trigger_forward": self._handle_trigger_forward,
        }
        
        logger.info("QueueWorker initialized: %s", self.worker_id)
    
    async def start(self):
        """Start the queue worker."""
        self.running = True
        self.stats["started_at"] = datetime.now(timezone.utc)
        
        logger.info("Starting queue worker: %s", self.worker_id)
        
        # Start listening for job notifications
        await self.queue.listen(
            job_type=None,  # Listen for all job types
            callback=self._process_jobs,
        )
        
        # Start cleanup task for stale jobs
        asyncio.create_task(self._cleanup_stale_jobs_periodic())
        
        # Main processing loop
        while self.running:
            try:
                await self._process_jobs()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in queue worker main loop: %s", e, exc_info=True)
                await asyncio.sleep(self.poll_interval)
    
    async def stop(self):
        """Stop the queue worker."""
        logger.info("Stopping queue worker: %s", self.worker_id)
        self.running = False
        await self.queue.stop_listening()
    
    async def _process_jobs(self):
        """Process available jobs from the queue."""
        try:
            # Dequeue jobs (up to batch_size)
            jobs = await self.queue.dequeue(batch_size=self.batch_size)
            
            if not jobs:
                return  # No jobs available
            
            logger.debug("Dequeued %d job(s) for processing", len(jobs))
            
            # Process each job
            for job in jobs:
                await self._process_job(job)
        
        except Exception as e:
            logger.error("Error processing jobs: %s", e, exc_info=True)
    
    async def _process_job(self, job: JobResult):
        """Process a single job.
        
        Args:
            job: JobResult object from queue
        """
        handler = self.handlers.get(job.job_type)
        
        if not handler:
            logger.warning("No handler for job type: %s (job_id: %s)", job.job_type, job.job_id)
            await self.queue.fail(
                job.job_id,
                error_message=f"Unknown job type: {job.job_type}",
                retry=False,
            )
            self.stats["failed"] += 1
            return
        
        try:
            logger.debug("Processing job: %s (type: %s, attempt: %d/%d)", 
                        job.job_id, job.job_type, job.attempts, job.max_attempts)
            
            # Execute handler
            result = await handler(job)
            
            # Mark job as completed
            await self.queue.complete(job.job_id, result=result)
            
            # Record metrics
            metrics = get_metrics_collector()
            metrics.record_queue_job(job_type=job.job_type, status="completed")
            
            self.stats["processed"] += 1
            self.stats["succeeded"] += 1
            
            logger.debug("Completed job: %s", job.job_id)
        
        except Exception as e:
            error_msg = str(e)
            logger.error("Job %s failed: %s", job.job_id, error_msg, exc_info=True)
            
            # Mark job as failed (will retry if attempts remain)
            await self.queue.fail(
                job.job_id,
                error_message=error_msg,
                retry=True,
            )
            
            # Record metrics
            metrics = get_metrics_collector()
            metrics.record_queue_job(job_type=job.job_type, status="failed")
            
            self.stats["processed"] += 1
            self.stats["failed"] += 1
    
    async def _handle_process_received_file(self, job: JobResult) -> Dict[str, Any]:
        """Handle process_received_file job.
        
        This extracts metadata from a received DICOM file and updates the database.
        
        Args:
            job: Job result with payload containing file_path, sop_instance_uid, etc.
        
        Returns:
            Dictionary with processing results
        """
        payload = job.payload
        file_path = Path(payload.get("file_path"))
        sop_instance_uid = payload.get("sop_instance_uid")
        study_instance_uid = payload.get("study_instance_uid")
        
        if not file_path.exists():
            raise FileNotFoundError(f"DICOM file not found: {file_path}")
        
        # Parse DICOM metadata
        dataset = parse_dicom_metadata(file_path)
        if not dataset:
            raise ValueError(f"Could not parse DICOM file: {file_path}")
        
        # Extract common tags
        tags = get_dicom_tags(
            dataset,
            "PatientID",
            "PatientName",
            "PatientBirthDate",
            "PatientSex",
            "StudyDate",
            "StudyTime",
            "AccessionNumber",
            "StudyDescription",
            "ReferringPhysicianName",
            "Modality",
            "InstitutionName",
            "SeriesInstanceUID",
            "SeriesNumber",
            "SeriesDate",
            "SeriesTime",
            "SeriesDescription",
            "BodyPartExamined",
            "ProtocolName",
            "SOPClassUID",
            "InstanceNumber",
            "ContentDate",
            "ContentTime",
            "TransferSyntaxUID",
        )
        
        # Update database with metadata
        async for session in get_db_session():
            # Find or create Study
            study_result = await session.execute(
                select(Study).where(Study.study_instance_uid == study_instance_uid)
            )
            study = study_result.scalar_one_or_none()
            
            if not study:
                # Create new study
                study = Study(
                    study_instance_uid=study_instance_uid,
                    patient_id=tags.get("PatientID"),
                    patient_name=str(tags.get("PatientName", "")) if tags.get("PatientName") else None,
                    patient_birth_date=tags.get("PatientBirthDate"),
                    patient_sex=tags.get("PatientSex"),
                    study_date=tags.get("StudyDate"),
                    study_time=tags.get("StudyTime"),
                    accession_number=tags.get("AccessionNumber"),
                    study_description=tags.get("StudyDescription"),
                    referring_physician_name=str(tags.get("ReferringPhysicianName", "")) if tags.get("ReferringPhysicianName") else None,
                    modality=tags.get("Modality"),
                    institution_name=tags.get("InstitutionName"),
                    storage_path=str(file_path.parent),
                    status="processing",
                )
                session.add(study)
                await session.flush()  # Get study.id
            else:
                # Update existing study
                study.status = "processing"
                study.file_count += 1
                study.total_size_bytes += file_path.stat().st_size
            
            # Find or create Series
            series_instance_uid = tags.get("SeriesInstanceUID")
            if series_instance_uid:
                series_result = await session.execute(
                    select(Series)
                    .where(Series.series_instance_uid == series_instance_uid)
                    .where(Series.study_id == study.id)
                )
                series = series_result.scalar_one_or_none()
                
                if not series:
                    series = Series(
                        study_id=study.id,
                        series_instance_uid=series_instance_uid,
                        series_number=tags.get("SeriesNumber"),
                        series_date=tags.get("SeriesDate"),
                        series_time=tags.get("SeriesTime"),
                        modality=tags.get("Modality"),
                        series_description=tags.get("SeriesDescription"),
                        body_part_examined=tags.get("BodyPartExamined"),
                        protocol_name=tags.get("ProtocolName"),
                    )
                    session.add(series)
                    await session.flush()
                else:
                    series.instance_count += 1
                    series.total_size_bytes += file_path.stat().st_size
            
            # Create or update Instance
            instance_result = await session.execute(
                select(Instance).where(Instance.sop_instance_uid == sop_instance_uid)
            )
            instance = instance_result.scalar_one_or_none()
            
            if not instance:
                instance = Instance(
                    series_id=series.id if series_instance_uid else None,
                    sop_instance_uid=sop_instance_uid,
                    sop_class_uid=tags.get("SOPClassUID", ""),
                    instance_number=tags.get("InstanceNumber"),
                    content_date=tags.get("ContentDate"),
                    content_time=tags.get("ContentTime"),
                    file_path=str(file_path),
                    file_size_bytes=file_path.stat().st_size,
                    transfer_syntax_uid=tags.get("TransferSyntaxUID"),
                    has_preamble=True,  # Assume true if file was received
                )
                session.add(instance)
            
            # Create ingest event
            ingest_event = IngestEvent(
                study_id=study.id,
                sop_instance_uid=sop_instance_uid,
                calling_ae_title=payload.get("calling_ae_title"),
                called_ae_title=payload.get("called_ae_title"),
                event_type="stored",
                status="success",
                receive_duration_ms=payload.get("receive_duration_ms"),
                storage_duration_ms=payload.get("storage_duration_ms"),
                file_size_bytes=file_path.stat().st_size,
            )
            session.add(ingest_event)
            
            await session.commit()
            break
        
        # Check if study is complete (all instances received)
        # TODO: Implement logic to determine study completeness
        
        # Trigger forwarding if configured
        # TODO: Check forwarding rules and create ForwardJob entries
        
        return {
            "study_instance_uid": study_instance_uid,
            "series_instance_uid": series_instance_uid,
            "sop_instance_uid": sop_instance_uid,
            "file_path": str(file_path),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _handle_extract_metadata(self, job: JobResult) -> Dict[str, Any]:
        """Handle extract_metadata job.
        
        Similar to process_received_file but focused only on metadata extraction.
        
        Args:
            job: Job result
        
        Returns:
            Dictionary with metadata
        """
        # Similar to process_received_file but lighter weight
        return await self._handle_process_received_file(job)
    
    async def _handle_trigger_forward(self, job: JobResult) -> Dict[str, Any]:
        """Handle trigger_forward job.
        
        Creates ForwardJob entries for forwarding a study to configured destinations.
        
        Args:
            job: Job result with payload containing study_instance_uid
        
        Returns:
            Dictionary with forwarding job IDs
        """
        payload = job.payload
        study_instance_uid = payload.get("study_instance_uid")
        
        if not study_instance_uid:
            raise ValueError("Missing study_instance_uid in payload")
        
        # Get study and enabled destinations
        async for session in get_db_session():
            from dicom_gw.database.models import Destination, ForwardJob
            
            # Get study
            study_result = await session.execute(
                select(Study).where(Study.study_instance_uid == study_instance_uid)
            )
            study = study_result.scalar_one_or_none()
            
            if not study:
                raise ValueError(f"Study not found: {study_instance_uid}")
            
            # Get enabled destinations
            destinations_result = await session.execute(
                select(Destination).where(Destination.enabled == True)  # noqa: E712
            )
            destinations = destinations_result.scalars().all()
            
            # Create ForwardJob for each destination
            forward_job_ids = []
            for destination in destinations:
                # Check forwarding rules if configured
                if destination.forwarding_rules:
                    # TODO: Implement rule matching logic
                    pass
                
                forward_job = ForwardJob(
                    study_id=study.id,
                    destination_id=destination.id,
                    status="pending",
                    priority=0,
                    max_attempts=3,
                )
                session.add(forward_job)
                forward_job_ids.append(str(forward_job.id))
            
            await session.commit()
            break
        
        return {
            "study_instance_uid": study_instance_uid,
            "forward_job_ids": forward_job_ids,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _cleanup_stale_jobs_periodic(self):
        """Periodically clean up stale jobs."""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self.queue.cleanup_stale_jobs(timeout_minutes=30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in stale job cleanup: %s", e, exc_info=True)
    
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
        metrics.update_worker_uptime("queue", self.worker_id, uptime_seconds)
        
        return {
            **self.stats,
            "uptime_seconds": uptime_seconds,
            "worker_id": self.worker_id,
            "queue_stats": {},  # TODO: Get from queue
        }


def main():
    """Main entry point for the queue worker service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create worker
    worker = QueueWorker()
    
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

