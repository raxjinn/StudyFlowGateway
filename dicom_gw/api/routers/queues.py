"""Queue endpoints."""

import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Path, Body
from pydantic import BaseModel

from dicom_gw.queue.job_queue import JobQueue
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import ForwardJob, Study
from sqlalchemy import select
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""
    pending: int
    processing: int
    completed: int
    failed: int
    dead_letter: int


class RetryRequest(BaseModel):
    """Retry job request."""
    job_ids: Optional[List[UUID]] = None


@router.get("/queues/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """Get queue statistics."""
    queue = JobQueue()
    stats = await queue.get_stats()
    
    return QueueStatsResponse(**stats)


@router.post("/queues/retry")
async def retry_jobs(request: RetryRequest = Body(...)):
    """Retry failed or dead-letter jobs."""
    async for session in get_db_session():
        if request.job_ids:
            # Retry specific jobs
            result = await session.execute(
                select(ForwardJob).where(ForwardJob.id.in_(request.job_ids))
            )
            jobs = result.scalars().all()
        else:
            # Retry all dead-letter jobs
            result = await session.execute(
                select(ForwardJob).where(ForwardJob.status == "dead_letter")
            )
            jobs = result.scalars().all()
        
        if not jobs:
            raise HTTPException(status_code=404, detail="No jobs found to retry")
        
        retried_count = 0
        for job in jobs:
            job.status = "pending"
            job.attempts = 0
            job.available_at = datetime.utcnow()
            job.error_message = None
            retried_count += 1
        
        await session.commit()
        
        return {
            "retried": retried_count,
            "job_ids": [str(job.id) for job in jobs],
        }


@router.post("/queues/replay/{study_instance_uid}")
async def replay_study(
    study_instance_uid: str = Path(...),
    destination_ids: Optional[List[UUID]] = Body(None),
):
    """Replay a study - create new forward jobs for a study."""
    async for session in get_db_session():
        # Find study
        result = await session.execute(
            select(Study).where(Study.study_instance_uid == study_instance_uid)
        )
        study = result.scalar_one_or_none()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        # Get destinations
        from dicom_gw.database.models import Destination
        
        if destination_ids:
            dest_result = await session.execute(
                select(Destination).where(Destination.id.in_(destination_ids))
            )
        else:
            dest_result = await session.execute(
                select(Destination).where(Destination.enabled == True)  # noqa: E712
            )
        
        destinations = dest_result.scalars().all()
        
        if not destinations:
            raise HTTPException(status_code=400, detail="No valid destinations found")
        
        # Create forward jobs
        forward_job_ids = []
        for destination in destinations:
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
        
        return {
            "study_instance_uid": study_instance_uid,
            "forward_job_ids": forward_job_ids,
            "destinations": [d.name for d in destinations],
        }

