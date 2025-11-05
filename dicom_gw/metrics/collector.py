"""Prometheus metrics collector for DICOM Gateway."""

import logging
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, generate_latest

logger = logging.getLogger(__name__)

# Create a custom registry for application metrics
registry = CollectorRegistry()

# Counter metrics (only increase)
ingest_events_total = Counter(
    'dicom_gw_ingest_events_total',
    'Total number of DICOM files received',
    ['status', 'ae_title'],
    registry=registry
)

forward_events_total = Counter(
    'dicom_gw_forward_events_total',
    'Total number of forwarding attempts',
    ['destination', 'status'],
    registry=registry
)

forward_bytes_total = Counter(
    'dicom_gw_forward_bytes_total',
    'Total bytes forwarded',
    ['destination'],
    registry=registry
)

queue_jobs_total = Counter(
    'dicom_gw_queue_jobs_total',
    'Total number of jobs processed',
    ['job_type', 'status'],
    registry=registry
)

# Histogram metrics (distribution of values)
ingest_duration_seconds = Histogram(
    'dicom_gw_ingest_duration_seconds',
    'Time to receive and store a DICOM file',
    ['ae_title'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
    registry=registry
)

forward_duration_seconds = Histogram(
    'dicom_gw_forward_duration_seconds',
    'Time to forward a study',
    ['destination'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=registry
)

ae_response_time_seconds = Histogram(
    'dicom_gw_ae_response_time_seconds',
    'Response time from remote AE',
    ['destination', 'operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

db_query_duration_seconds = Histogram(
    'dicom_gw_db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=registry
)

# Gauge metrics (current value, can go up or down)
queue_depth = Gauge(
    'dicom_gw_queue_depth',
    'Current number of pending jobs',
    ['job_type'],
    registry=registry
)

processing_jobs = Gauge(
    'dicom_gw_processing_jobs',
    'Current number of jobs being processed',
    ['job_type'],
    registry=registry
)

db_pool_size = Gauge(
    'dicom_gw_db_pool_size',
    'Database connection pool size',
    ['state'],  # active, idle, waiting
    registry=registry
)

db_pool_connections = Gauge(
    'dicom_gw_db_pool_connections',
    'Database connection pool connections',
    ['state'],  # min, max, current
    registry=registry
)

studies_received_total = Gauge(
    'dicom_gw_studies_received_total',
    'Total number of studies received',
    registry=registry
)

studies_forwarded_total = Gauge(
    'dicom_gw_studies_forwarded_total',
    'Total number of studies forwarded',
    registry=registry
)

active_destinations = Gauge(
    'dicom_gw_active_destinations',
    'Number of active destinations',
    registry=registry
)

worker_uptime_seconds = Gauge(
    'dicom_gw_worker_uptime_seconds',
    'Worker uptime in seconds',
    ['worker_type', 'worker_id'],
    registry=registry
)

# Info metric (key-value pairs)
build_info = Info(
    'dicom_gw_build_info',
    'Build information',
    registry=registry
)

# Initialize build info
build_info.info({
    'version': '0.1.0',
    'name': 'dicom-gateway',
})


class MetricsCollector:
    """Centralized metrics collector."""
    
    @staticmethod
    def record_ingest(
        status: str,
        duration_seconds: float,
        ae_title: str = "unknown",
        file_size_bytes: int = 0,  # noqa: ARG004
    ):
        """Record a DICOM file ingestion event.
        
        Args:
            status: Event status (success, failed)
            duration_seconds: Time to receive and store
            ae_title: Calling AE title
            file_size_bytes: File size in bytes (for future use)
        """
        ingest_events_total.labels(status=status, ae_title=ae_title).inc()
        ingest_duration_seconds.labels(ae_title=ae_title).observe(duration_seconds)
        
        if status == "success":
            studies_received_total.inc()
    
    @staticmethod
    def record_forward(
        destination: str,
        status: str,
        duration_seconds: float,
        bytes_sent: int = 0,
    ):
        """Record a forwarding event.
        
        Args:
            destination: Destination name
            status: Forward status (success, failed)
            duration_seconds: Time to forward
            bytes_sent: Bytes sent
        """
        forward_events_total.labels(destination=destination, status=status).inc()
        forward_duration_seconds.labels(destination=destination).observe(duration_seconds)
        
        if status == "success":
            forward_bytes_total.labels(destination=destination).inc(bytes_sent)
            studies_forwarded_total.inc()
    
    @staticmethod
    def record_ae_response(
        destination: str,
        operation: str,
        duration_seconds: float,
    ):
        """Record AE response time.
        
        Args:
            destination: Destination name
            operation: Operation type (c_store, c_echo)
            duration_seconds: Response time
        """
        ae_response_time_seconds.labels(
            destination=destination,
            operation=operation
        ).observe(duration_seconds)
    
    @staticmethod
    def record_queue_job(
        job_type: str,
        status: str,
    ):
        """Record a queue job event.
        
        Args:
            job_type: Job type (process_received_file, etc.)
            status: Job status (completed, failed)
        """
        queue_jobs_total.labels(job_type=job_type, status=status).inc()
    
    @staticmethod
    def update_queue_depth(job_type: str, depth: int):
        """Update queue depth.
        
        Args:
            job_type: Job type
            depth: Current queue depth
        """
        queue_depth.labels(job_type=job_type).set(depth)
    
    @staticmethod
    def update_processing_jobs(job_type: str, count: int):
        """Update number of processing jobs.
        
        Args:
            job_type: Job type
            count: Number of jobs being processed
        """
        processing_jobs.labels(job_type=job_type).set(count)
    
    @staticmethod
    def update_db_pool(active: int, idle: int, waiting: int, min_size: int, max_size: int, current: int):
        """Update database pool metrics.
        
        Args:
            active: Active connections
            idle: Idle connections
            waiting: Connections waiting
            min_size: Minimum pool size
            max_size: Maximum pool size
            current: Current pool size
        """
        db_pool_size.labels(state="active").set(active)
        db_pool_size.labels(state="idle").set(idle)
        db_pool_size.labels(state="waiting").set(waiting)
        db_pool_connections.labels(state="min").set(min_size)
        db_pool_connections.labels(state="max").set(max_size)
        db_pool_connections.labels(state="current").set(current)
    
    @staticmethod
    def update_active_destinations(count: int):
        """Update active destinations count.
        
        Args:
            count: Number of active destinations
        """
        active_destinations.set(count)
    
    @staticmethod
    def update_worker_uptime(worker_type: str, worker_id: str, uptime_seconds: float):
        """Update worker uptime.
        
        Args:
            worker_type: Type of worker (queue, forwarder, dbpool)
            worker_id: Worker ID
            uptime_seconds: Uptime in seconds
        """
        worker_uptime_seconds.labels(
            worker_type=worker_type,
            worker_id=worker_id
        ).set(uptime_seconds)
    
    @staticmethod
    def record_db_query(operation: str, duration_seconds: float):
        """Record database query duration.
        
        Args:
            operation: Operation type (select, insert, update, delete)
            duration_seconds: Query duration
        """
        db_query_duration_seconds.labels(operation=operation).observe(duration_seconds)
    
    @staticmethod
    def generate_metrics() -> bytes:
        """Generate Prometheus metrics output.
        
        Returns:
            Bytes of Prometheus metrics in text format
        """
        return generate_latest(registry)


# Global metrics collector instance
_metrics_collector: MetricsCollector = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector  # noqa: PLW0603
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

