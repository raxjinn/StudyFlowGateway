"""Metrics endpoints."""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

from dicom_gw.queue.job_queue import JobQueue
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import Study, Destination
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

router = APIRouter()


class MetricsResponse(BaseModel):
    """Metrics response model."""
    queue_stats: dict
    worker_stats: dict
    scp_stats: dict
    scu_stats: dict
    studies_stats: dict
    destinations_stats: dict


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get system metrics."""
    # Get queue statistics
    queue = JobQueue()
    queue_stats = await queue.get_stats()
    
    # Get worker statistics (if workers are running, this would be from a shared state)
    # For now, return placeholder
    worker_stats = {
        "queue_worker": {},
        "forwarder_worker": {},
        "dbpool_worker": {},
    }
    
    # Get SCP/SCU statistics (if instances exist)
    scp_stats = {}
    scu_stats = {}
    
    # Get studies statistics
    studies_stats = {
        "total": 0,
        "by_status": {},
    }
    
    async for session in get_db_session():
        # Count total studies
        total_result = await session.execute(
            select(func.count(Study.id))
        )
        studies_stats["total"] = total_result.scalar() or 0
        
        # Count by status
        status_result = await session.execute(
            select(Study.status, func.count(Study.id))
            .group_by(Study.status)
        )
        for status, count in status_result.all():
            studies_stats["by_status"][status] = count
        
        # Count active destinations
        dest_result = await session.execute(
            select(func.count(Destination.id))
            .where(Destination.enabled == True)  # noqa: E712
        )
        active_dests = dest_result.scalar() or 0
        
        # Update metrics
        from dicom_gw.metrics.collector import get_metrics_collector
        metrics = get_metrics_collector()
        metrics.update_active_destinations(active_dests)
        
        destinations_stats = {
            "active": active_dests,
            "total": 0,
        }
        
        total_dest_result = await session.execute(
            select(func.count(Destination.id))
        )
        destinations_stats["total"] = total_dest_result.scalar() or 0
        
        break
    
    return MetricsResponse(
        queue_stats=queue_stats,
        worker_stats=worker_stats,
        scp_stats=scp_stats,
        scu_stats=scu_stats,
        studies_stats=studies_stats,
        destinations_stats=destinations_stats,
    )


@router.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    from fastapi.responses import Response
    from dicom_gw.metrics.collector import get_metrics_collector
    
    collector = get_metrics_collector()
    metrics_output = collector.generate_metrics()
    
    return Response(
        content=metrics_output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )

