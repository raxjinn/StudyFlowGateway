"""Worker Autoscaler Service.

This service monitors queue depth, job processing rates, and worker utilization
to automatically scale worker instances up or down based on load.
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Dict, Any

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import Job, ForwardJob
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


class WorkerAutoscaler:
    """Automatic scaler for worker instances based on queue metrics."""
    
    def __init__(
        self,
        check_interval: float = 30.0,
        scale_up_threshold_pending: int = 50,
        scale_up_threshold_processing: int = 10,
        scale_down_threshold_pending: int = 5,
        scale_down_threshold_processing: int = 2,
        min_workers: Dict[str, int] = None,
        max_workers: Dict[str, int] = None,
        scale_up_cooldown: int = 60,
        scale_down_cooldown: int = 300,
    ):
        """Initialize autoscaler.
        
        Args:
            check_interval: Seconds between scaling checks
            scale_up_threshold_pending: Pending jobs threshold to scale up
            scale_up_threshold_processing: Processing jobs threshold to scale up
            scale_down_threshold_pending: Pending jobs threshold to scale down
            scale_down_threshold_processing: Processing jobs threshold to scale down
            min_workers: Minimum workers per type (default: {"queue": 1, "forwarder": 1, "dbpool": 1})
            max_workers: Maximum workers per type (default: {"queue": 10, "forwarder": 20, "dbpool": 5})
            scale_up_cooldown: Seconds to wait before scaling up again
            scale_down_cooldown: Seconds to wait before scaling down again
        """
        self.check_interval = check_interval
        self.scale_up_threshold_pending = scale_up_threshold_pending
        self.scale_up_threshold_processing = scale_up_threshold_processing
        self.scale_down_threshold_pending = scale_down_threshold_pending
        self.scale_down_threshold_processing = scale_down_threshold_processing
        
        self.min_workers = min_workers or {"queue": 1, "forwarder": 1, "dbpool": 1}
        self.max_workers = max_workers or {"queue": 10, "forwarder": 20, "dbpool": 5}
        
        self.scale_up_cooldown = scale_up_cooldown
        self.scale_down_cooldown = scale_down_cooldown
        
        self.running = False
        self.last_scale_up: Dict[str, float] = {}
        self.last_scale_down: Dict[str, float] = {}
        
        # Import subprocess for systemctl commands
        import subprocess
        self.subprocess = subprocess
        
        logger.info("WorkerAutoscaler initialized")
        logger.info("  Min workers: %s", self.min_workers)
        logger.info("  Max workers: %s", self.max_workers)
        logger.info("  Scale up thresholds: pending=%d, processing=%d", 
                   scale_up_threshold_pending, scale_up_threshold_processing)
        logger.info("  Scale down thresholds: pending=%d, processing=%d",
                   scale_down_threshold_pending, scale_down_threshold_processing)
    
    async def start(self):
        """Start the autoscaler."""
        self.running = True
        logger.info("Starting worker autoscaler (check interval: %.1fs)", self.check_interval)
        
        while self.running:
            try:
                await self._check_and_scale()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in autoscaler loop: %s", e, exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """Stop the autoscaler."""
        logger.info("Stopping worker autoscaler")
        self.running = False
    
    async def _check_and_scale(self):
        """Check queue metrics and scale workers if needed."""
        try:
            # Get queue metrics
            queue_metrics = await self._get_queue_metrics()
            forward_metrics = await self._get_forward_metrics()
            
            # Get current worker counts
            current_workers = await self._get_current_worker_counts()
            
            logger.debug("Queue metrics: %s", queue_metrics)
            logger.debug("Forward metrics: %s", forward_metrics)
            logger.debug("Current workers: %s", current_workers)
            
            # Scale queue workers
            await self._scale_worker_type(
                "queue",
                queue_metrics["pending"],
                queue_metrics["processing"],
                current_workers.get("queue", 0),
            )
            
            # Scale forwarder workers
            await self._scale_worker_type(
                "forwarder",
                forward_metrics["pending"],
                forward_metrics["processing"],
                current_workers.get("forwarder", 0),
            )
            
            # Scale dbpool workers (less dynamic, based on queue depth)
            await self._scale_worker_type(
                "dbpool",
                queue_metrics["pending"],  # Use general queue depth
                queue_metrics["processing"],
                current_workers.get("dbpool", 0),
            )
            
        except Exception as e:
            logger.error("Error checking and scaling: %s", e, exc_info=True)
    
    async def _get_queue_metrics(self) -> Dict[str, int]:
        """Get job queue metrics.
        
        Returns:
            Dictionary with pending and processing job counts
        """
        metrics = {"pending": 0, "processing": 0}
        
        try:
            async for session in get_db_session():
                # Count pending jobs
                pending_result = await session.execute(
                    select(func.count(Job.id)).where(Job.status == "pending")
                )
                metrics["pending"] = pending_result.scalar() or 0
                
                # Count processing jobs
                processing_result = await session.execute(
                    select(func.count(Job.id)).where(Job.status == "processing")
                )
                metrics["processing"] = processing_result.scalar() or 0
                break
        except Exception as e:  # noqa: BLE001
            logger.warning("Error getting queue metrics: %s", e)
        
        return metrics
    
    async def _get_forward_metrics(self) -> Dict[str, int]:
        """Get forward job queue metrics.
        
        Returns:
            Dictionary with pending and processing forward job counts
        """
        metrics = {"pending": 0, "processing": 0}
        
        try:
            async for session in get_db_session():
                # Count pending forward jobs
                pending_result = await session.execute(
                    select(func.count(ForwardJob.id)).where(ForwardJob.status == "pending")
                )
                metrics["pending"] = pending_result.scalar() or 0
                
                # Count processing forward jobs
                processing_result = await session.execute(
                    select(func.count(ForwardJob.id)).where(ForwardJob.status == "processing")
                )
                metrics["processing"] = processing_result.scalar() or 0
                break
        except Exception as e:  # noqa: BLE001
            logger.warning("Error getting forward metrics: %s", e)
        
        return metrics
    
    async def _get_current_worker_counts(self) -> Dict[str, int]:
        """Get current running worker instance counts.
        
        Returns:
            Dictionary with worker type -> count
        """
        counts = {"queue": 0, "forwarder": 0, "dbpool": 0}
        
        try:
            # Use systemctl to check running instances
            for worker_type in ["queue", "forwarder", "dbpool"]:
                service_pattern = f"dicom-gw-{worker_type}-worker@"
                
                # Check running instances (run in thread to avoid blocking)
                result = await asyncio.to_thread(
                    self.subprocess.run,
                    ["systemctl", "list-units", "--type=service", "--state=running", 
                     "--no-pager", "--no-legend", f"{service_pattern}*"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                
                if result.returncode == 0:
                    # Count matching lines
                    lines = [l for l in result.stdout.strip().split('\n') if l.strip() and service_pattern in l]
                    counts[worker_type] = len(lines)
        
        except Exception as e:
            logger.warning("Error getting worker counts: %s", e)
        
        return counts
    
    async def _scale_worker_type(
        self,
        worker_type: str,
        pending: int,
        processing: int,
        current_count: int,
    ):
        """Scale a specific worker type.
        
        Args:
            worker_type: Type of worker (queue, forwarder, dbpool)
            pending: Number of pending jobs
            processing: Number of processing jobs
            current_count: Current number of running workers
        """
        min_count = self.min_workers.get(worker_type, 1)
        max_count = self.max_workers.get(worker_type, 10)
        
        # Determine target count
        target_count = current_count
        
        # Check if we should scale up
        if (pending >= self.scale_up_threshold_pending or 
            processing >= self.scale_up_threshold_processing):
            if current_count < max_count:
                # Check cooldown
                last_scale_up_time = self.last_scale_up.get(worker_type, 0)
                if time.time() - last_scale_up_time >= self.scale_up_cooldown:
                    target_count = min(current_count + 1, max_count)
                    logger.info(
                        "Scaling UP %s workers: %d -> %d (pending=%d, processing=%d)",
                        worker_type, current_count, target_count, pending, processing
                    )
                    await self._scale_workers(worker_type, target_count)
                    self.last_scale_up[worker_type] = time.time()
        
        # Check if we should scale down
        elif (pending <= self.scale_down_threshold_pending and 
              processing <= self.scale_down_threshold_processing):
            if current_count > min_count:
                # Check cooldown
                last_scale_down_time = self.last_scale_down.get(worker_type, 0)
                if time.time() - last_scale_down_time >= self.scale_down_cooldown:
                    target_count = max(current_count - 1, min_count)
                    logger.info(
                        "Scaling DOWN %s workers: %d -> %d (pending=%d, processing=%d)",
                        worker_type, current_count, target_count, pending, processing
                    )
                    await self._scale_workers(worker_type, target_count)
                    self.last_scale_down[worker_type] = time.time()
    
    async def _scale_workers(self, worker_type: str, target_count: int):
        """Scale workers to target count.
        
        Args:
            worker_type: Type of worker (queue, forwarder, dbpool)
            target_count: Target number of workers
        """
        try:
            # Get current running instances
            current_workers = await self._get_current_worker_counts()
            current_count = current_workers.get(worker_type, 0)
            
            if target_count > current_count:
                # Scale up - start new instances
                for i in range(current_count, target_count):
                    instance_id = str(i)
                    service_name = f"dicom-gw-{worker_type}-worker@{instance_id}"
                    
                    # Enable and start service
                    enable_result = await asyncio.to_thread(
                        self.subprocess.run,
                        ["systemctl", "enable", service_name],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    
                    if enable_result.returncode == 0:
                        start_result = await asyncio.to_thread(
                            self.subprocess.run,
                            ["systemctl", "start", service_name],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        
                        if start_result.returncode == 0:
                            logger.info("Started %s", service_name)
                        else:
                            logger.error("Failed to start %s: %s", service_name, start_result.stderr)
                    else:
                        logger.error("Failed to enable %s: %s", service_name, enable_result.stderr)
                    
                    # Small delay between starts
                    await asyncio.sleep(1)
            
            elif target_count < current_count:
                # Scale down - stop instances
                # Stop from highest instance number down
                for i in range(current_count - 1, target_count - 1, -1):
                    instance_id = str(i)
                    service_name = f"dicom-gw-{worker_type}-worker@{instance_id}"
                    
                    # Stop and disable service
                    stop_result = await asyncio.to_thread(
                        self.subprocess.run,
                        ["systemctl", "stop", service_name],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    
                    if stop_result.returncode == 0:
                        disable_result = await asyncio.to_thread(
                            self.subprocess.run,
                            ["systemctl", "disable", service_name],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        
                        if disable_result.returncode == 0:
                            logger.info("Stopped and disabled %s", service_name)
                        else:
                            logger.error("Failed to disable %s: %s", service_name, disable_result.stderr)
                    else:
                        logger.error("Failed to stop %s: %s", service_name, stop_result.stderr)
                    
                    # Small delay between stops
                    await asyncio.sleep(1)
            
            # Note: We'd need to add autoscaler metrics to the collector if we want to track this
            # metrics = get_metrics_collector()
            
        except Exception as e:  # noqa: BLE001
            logger.error("Error scaling workers: %s", e, exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get autoscaler status.
        
        Returns:
            Dictionary with autoscaler status
        """
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "min_workers": self.min_workers,
            "max_workers": self.max_workers,
            "last_scale_up": self.last_scale_up,
            "last_scale_down": self.last_scale_down,
        }


def main():
    """Main entry point for the autoscaler service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Load YAML config for autoscaler settings
    try:
        from dicom_gw.config.yaml_config import GatewayConfig
        from pathlib import Path
        config_path = Path("/etc/dicom-gw/config.yaml")
        if config_path.exists():
            config = GatewayConfig.from_yaml(config_path)
            worker_config = config.workers
        else:
            worker_config = None
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not load YAML config, using defaults: %s", e)
        worker_config = None
    
    # Get autoscaler configuration from YAML or use defaults
    if worker_config and hasattr(worker_config, 'autoscaler_enabled') and worker_config.autoscaler_enabled:
        check_interval = getattr(worker_config, 'autoscaler_check_interval', 30.0)
        scale_up_pending = getattr(worker_config, 'autoscaler_scale_up_threshold_pending', 50)
        scale_up_processing = getattr(worker_config, 'autoscaler_scale_up_threshold_processing', 10)
        scale_down_pending = getattr(worker_config, 'autoscaler_scale_down_threshold_pending', 5)
        scale_down_processing = getattr(worker_config, 'autoscaler_scale_down_threshold_processing', 2)
        min_queue = getattr(worker_config, 'autoscaler_min_workers_queue', 1)
        min_forwarder = getattr(worker_config, 'autoscaler_min_workers_forwarder', 1)
        min_dbpool = getattr(worker_config, 'autoscaler_min_workers_dbpool', 1)
        max_queue = getattr(worker_config, 'autoscaler_max_workers_queue', 10)
        max_forwarder = getattr(worker_config, 'autoscaler_max_workers_forwarder', 20)
        max_dbpool = getattr(worker_config, 'autoscaler_max_workers_dbpool', 5)
        scale_up_cooldown = getattr(worker_config, 'autoscaler_scale_up_cooldown', 60)
        scale_down_cooldown = getattr(worker_config, 'autoscaler_scale_down_cooldown', 300)
    else:
        # Use defaults
        check_interval = 30.0
        scale_up_pending = 50
        scale_up_processing = 10
        scale_down_pending = 5
        scale_down_processing = 2
        min_queue = 1
        min_forwarder = 1
        min_dbpool = 1
        max_queue = 10
        max_forwarder = 20
        max_dbpool = 5
        scale_up_cooldown = 60
        scale_down_cooldown = 300
    
    # Create autoscaler
    autoscaler = WorkerAutoscaler(
        check_interval=check_interval,
        scale_up_threshold_pending=scale_up_pending,
        scale_up_threshold_processing=scale_up_processing,
        scale_down_threshold_pending=scale_down_pending,
        scale_down_threshold_processing=scale_down_processing,
        min_workers={"queue": min_queue, "forwarder": min_forwarder, "dbpool": min_dbpool},
        max_workers={"queue": max_queue, "forwarder": max_forwarder, "dbpool": max_dbpool},
        scale_up_cooldown=scale_up_cooldown,
        scale_down_cooldown=scale_down_cooldown,
    )
    
    # Setup signal handlers
    def signal_handler(signum, _frame):
        logger.info("Received signal %d, shutting down...", signum)
        asyncio.create_task(autoscaler.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run autoscaler
    try:
        asyncio.run(autoscaler.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        asyncio.run(autoscaler.stop())


if __name__ == "__main__":
    main()

