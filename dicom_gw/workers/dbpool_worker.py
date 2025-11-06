"""DB Pool Worker Service.

This worker handles asynchronous database writes with batch operations for
improved performance. It batches metadata writes, metrics, and other database
operations to reduce database load.
"""

import asyncio
import logging
import signal
import sys
from collections import defaultdict
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from sqlalchemy import select, insert, update

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.pool import get_asyncpg_pool
from dicom_gw.database.models import (
    IngestEvent,
    MetricsRollup,
    Study,
    Series,
    Instance,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchOperation:
    """Represents a batched database operation."""
    operation_type: str  # insert, update, delete
    model_class: type
    records: List[Dict[str, Any]] = field(default_factory=list)
    max_batch_size: int = 100


class DBPoolWorker:
    """Worker that batches database writes for improved performance."""
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        batch_interval: float = 5.0,
        max_batch_size: int = 100,
    ):
        """Initialize DB pool worker.
        
        Args:
            worker_id: Optional worker identifier
            batch_interval: Seconds between batch flushes
            max_batch_size: Maximum records per batch
        """
        # Use asyncio.get_running_loop() or create new event loop for worker ID
        try:
            loop = asyncio.get_running_loop()
            worker_suffix = loop.time()
        except RuntimeError:
            # No running loop, use time.time() instead
            import time
            worker_suffix = time.time()
        self.worker_id = worker_id or f"dbpool-worker-{worker_suffix}"
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
        self.running = False
        
        # Batch queues for different operations
        self.batches: Dict[str, BatchOperation] = defaultdict(
            lambda: BatchOperation(
                operation_type="insert",
                model_class=None,
                max_batch_size=max_batch_size,
            )
        )
        
        self.stats = {
            "batches_flushed": 0,
            "records_processed": 0,
            "errors": 0,
            "started_at": None,
        }
        
        logger.info("DBPoolWorker initialized: %s", self.worker_id)
    
    async def start(self):
        """Start the DB pool worker."""
        self.running = True
        from datetime import timezone
        self.stats["started_at"] = datetime.now(timezone.utc)
        
        logger.info("Starting DB pool worker: %s", self.worker_id)
        
        # Start periodic batch flush
        flush_task = asyncio.create_task(self._periodic_flush())
        
        # Main loop (just wait for flush task)
        try:
            await flush_task
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop the DB pool worker."""
        logger.info("Stopping DB pool worker: %s", self.worker_id)
        self.running = False
        
        # Flush any remaining batches
        await self._flush_all_batches()
    
    async def queue_insert(self, model_class: type, records: List[Dict[str, Any]]):
        """Queue records for batch insert.
        
        Args:
            model_class: SQLAlchemy model class
            records: List of dictionaries with record data
        """
        batch_key = f"insert_{model_class.__name__}"
        
        if batch_key not in self.batches:
            self.batches[batch_key] = BatchOperation(
                operation_type="insert",
                model_class=model_class,
                max_batch_size=self.max_batch_size,
            )
        
        self.batches[batch_key].records.extend(records)
        
        # Flush if batch is full
        if len(self.batches[batch_key].records) >= self.max_batch_size:
            await self._flush_batch(batch_key)
    
    async def queue_ingest_event(self, event_data: Dict[str, Any]):
        """Queue an ingest event for batch insert.
        
        Args:
            event_data: Dictionary with IngestEvent fields
        """
        await self.queue_insert(IngestEvent, [event_data])
    
    async def queue_metrics(self, metrics: List[Dict[str, Any]]):
        """Queue metrics for batch insert.
        
        Args:
            metrics: List of dictionaries with MetricsRollup fields
        """
        await self.queue_insert(MetricsRollup, metrics)
    
    async def _periodic_flush(self):
        """Periodically flush all batches."""
        while self.running:
            try:
                await asyncio.sleep(self.batch_interval)
                if self.running:
                    await self._flush_all_batches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic flush: %s", e, exc_info=True)
    
    async def _flush_all_batches(self):
        """Flush all pending batches."""
        batch_keys = list(self.batches.keys())
        
        for batch_key in batch_keys:
            if self.batches[batch_key].records:
                await self._flush_batch(batch_key)
    
    async def _flush_batch(self, batch_key: str):
        """Flush a specific batch.
        
        Args:
            batch_key: Key identifying the batch
        """
        if batch_key not in self.batches:
            return
        
        batch = self.batches[batch_key]
        
        if not batch.records:
            return
        
        # Process records in chunks
        records_to_process = batch.records[:batch.max_batch_size]
        batch.records = batch.records[batch.max_batch_size:]
        
        try:
            if batch.operation_type == "insert":
                await self._batch_insert(batch.model_class, records_to_process)
            
            self.stats["batches_flushed"] += 1
            self.stats["records_processed"] += len(records_to_process)
            
            logger.debug(
                "Flushed batch %s: %d records",
                batch_key,
                len(records_to_process),
            )
        
        except Exception as e:
            logger.error(
                "Error flushing batch %s: %s",
                batch_key,
                e,
                exc_info=True,
            )
            self.stats["errors"] += 1
            
            # Optionally re-queue failed records
            # For now, we'll just log the error
    
    async def _batch_insert(
        self, model_class: type, records: List[Dict[str, Any]]
    ):
        """Perform batch insert using asyncpg COPY or multirow INSERT.
        
        Args:
            model_class: SQLAlchemy model class
            records: List of dictionaries with record data
        """
        if not records:
            return
        
        # Use asyncpg pool for high-performance batch inserts
        pool = get_asyncpg_pool()
        await pool.initialize()
        
        # Get table name
        table_name = model_class.__tablename__
        
        try:
            # Convert records to tuples for COPY
            # Get column names from first record
            if not records:
                return
            
            # For asyncpg COPY, we need to prepare the data
            # For now, use SQLAlchemy bulk insert which is still efficient
            async for session in get_db_session():
                # Use bulk_insert_mappings for efficient batch insert
                await session.execute(
                    insert(model_class).values(records)
                )
                await session.commit()
                break
        
        except Exception as e:
            logger.error(
                "Error in batch insert for %s: %s",
                table_name,
                e,
                exc_info=True,
            )
            raise
    
    async def batch_update_study_metrics(self):
        """Update study metrics in batch (file count, total size, etc.)."""
        async for session in get_db_session():
            # This would update aggregated metrics for studies
            # For example, counting instances per study
            # Using a more efficient approach with subqueries
            
            # Update file_count and total_size_bytes for studies
            # This is a simplified version - in production, you might use
            # a more complex query with JOINs and aggregations
            
            result = await session.execute(
                select(Study.id, Study.study_instance_uid)
                .where(Study.status == "processing")
            )
            studies = result.all()
            
            for study_id, _ in studies:
                # Count instances for this study
                instance_count_result = await session.execute(
                    select(Instance)
                    .join(Series)
                    .where(Series.study_id == study_id)
                )
                instances = instance_count_result.scalars().all()
                
                if instances:
                    file_count = len(instances)
                    total_size = sum(inst.file_size_bytes for inst in instances if inst.file_size_bytes)
                    
                    await session.execute(
                        update(Study)
                        .where(Study.id == study_id)
                        .values(
                            file_count=file_count,
                            total_size_bytes=total_size,
                        )
                    )
            
            await session.commit()
            break
    
    async def aggregate_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        bucket_duration_minutes: int = 5,
    ):
        """Aggregate metrics from ingest_events into metrics_rollup.
        
        Args:
            start_time: Start time for aggregation
            end_time: End time for aggregation
            bucket_duration_minutes: Duration of each time bucket
        """
        async for session in get_db_session():
            # Aggregate ingest events into time buckets
            # This is a simplified version - in production, use proper SQL aggregation
            
            current_time = start_time
            metrics_to_insert = []
            
            while current_time < end_time:
                bucket_end = current_time + timedelta(minutes=bucket_duration_minutes)
                
                # Count events in this bucket
                result = await session.execute(
                    select(IngestEvent)
                    .where(IngestEvent.created_at >= current_time)
                    .where(IngestEvent.created_at < bucket_end)
                )
                events = result.scalars().all()
                
                if events:
                    # Create metrics
                    success_count = sum(1 for e in events if e.status == "success")
                    failed_count = sum(1 for e in events if e.status == "failed")
                    total_bytes = sum(e.file_size_bytes or 0 for e in events if e.file_size_bytes)
                    events_with_duration = [
                        e for e in events if e.receive_duration_ms
                    ]
                    avg_receive_ms = (
                        sum(e.receive_duration_ms or 0 for e in events_with_duration)
                        / len(events_with_duration)
                        if events_with_duration
                        else 0
                    )
                    
                    metrics_to_insert.extend([
                        {
                            "bucket_start": current_time,
                            "bucket_duration_minutes": bucket_duration_minutes,
                            "metric_name": "ingest_events_total",
                            "metric_value": len(events),
                            "metric_type": "counter",
                            "labels": {},
                        },
                        {
                            "bucket_start": current_time,
                            "bucket_duration_minutes": bucket_duration_minutes,
                            "metric_name": "ingest_events_success",
                            "metric_value": success_count,
                            "metric_type": "counter",
                            "labels": {},
                        },
                        {
                            "bucket_start": current_time,
                            "bucket_duration_minutes": bucket_duration_minutes,
                            "metric_name": "ingest_events_failed",
                            "metric_value": failed_count,
                            "metric_type": "counter",
                            "labels": {},
                        },
                        {
                            "bucket_start": current_time,
                            "bucket_duration_minutes": bucket_duration_minutes,
                            "metric_name": "ingest_bytes_total",
                            "metric_value": total_bytes,
                            "metric_type": "counter",
                            "labels": {},
                        },
                        {
                            "bucket_start": current_time,
                            "bucket_duration_minutes": bucket_duration_minutes,
                            "metric_name": "ingest_duration_avg_ms",
                            "metric_value": int(avg_receive_ms) if avg_receive_ms else 0,
                            "metric_type": "gauge",
                            "labels": {},
                        },
                    ])
                
                current_time = bucket_end
            
            if metrics_to_insert:
                await self.queue_metrics(metrics_to_insert)
                await self._flush_all_batches()
            
            break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.
        
        Returns:
            Dictionary with statistics
        """
        uptime_seconds = 0
        if self.stats["started_at"]:
            uptime_seconds = (datetime.now(timezone.utc) - self.stats["started_at"]).total_seconds()
        
        pending_records = sum(len(batch.records) for batch in self.batches.values())
        
        return {
            **self.stats,
            "uptime_seconds": uptime_seconds,
            "worker_id": self.worker_id,
            "pending_batches": len([b for b in self.batches.values() if b.records]),
            "pending_records": pending_records,
        }


def main():
    """Main entry point for the DB pool worker service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create worker
    worker = DBPoolWorker()
    
    # Setup signal handlers
    def signal_handler(signum, frame):  # pylint: disable=unused-argument
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

