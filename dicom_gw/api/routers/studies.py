"""Studies endpoints."""

import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel
from datetime import datetime

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import Study, ForwardJob, Destination
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

router = APIRouter()


class StudySummary(BaseModel):
    """Study summary model."""
    id: UUID
    study_instance_uid: str
    patient_id: Optional[str]
    patient_name: Optional[str]
    study_date: Optional[str]
    accession_number: Optional[str]
    modality: Optional[str]
    status: str
    file_count: int
    total_size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class StudyDetail(StudySummary):
    """Detailed study model."""
    study_time: Optional[str]
    study_description: Optional[str]
    referring_physician_name: Optional[str]
    institution_name: Optional[str]
    forwarded_at: Optional[datetime]


class ForwardRequest(BaseModel):
    """Forward study request model."""
    destination_ids: List[UUID]
    priority: int = 0


@router.get("/studies", response_model=List[StudySummary])
async def list_studies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    study_date: Optional[str] = None,
):
    """List studies with pagination and filtering."""
    async for session in get_db_session():
        query = select(Study)
        
        if status:
            query = query.where(Study.status == status)
        if patient_id:
            query = query.where(Study.patient_id == patient_id)
        if study_date:
            query = query.where(Study.study_date == study_date)
        
        query = query.order_by(Study.created_at.desc()).offset(skip).limit(limit)
        
        result = await session.execute(query)
        studies = result.scalars().all()
        
        return [StudySummary.model_validate(study) for study in studies]


@router.get("/studies/{study_id}", response_model=StudyDetail)
async def get_study(study_id: UUID = Path(...)):
    """Get study details by ID."""
    async for session in get_db_session():
        result = await session.execute(
            select(Study).where(Study.id == study_id)
        )
        study = result.scalar_one_or_none()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        return StudyDetail.model_validate(study)


@router.get("/studies/uid/{study_instance_uid}", response_model=StudyDetail)
async def get_study_by_uid(study_instance_uid: str = Path(...)):
    """Get study details by Study Instance UID."""
    async for session in get_db_session():
        result = await session.execute(
            select(Study).where(Study.study_instance_uid == study_instance_uid)
        )
        study = result.scalar_one_or_none()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        return StudyDetail.model_validate(study)


@router.post("/studies/{study_id}/forward")
async def forward_study(
    study_id: UUID = Path(...),
    request: ForwardRequest = None,
):
    """Forward a study to one or more destinations."""
    if not request:
        request = ForwardRequest(destination_ids=[])
    
    async for session in get_db_session():
        # Verify study exists
        study_result = await session.execute(
            select(Study).where(Study.id == study_id)
        )
        study = study_result.scalar_one_or_none()
        
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        
        # If no destinations specified, forward to all enabled destinations
        if not request.destination_ids:
            dest_result = await session.execute(
                select(Destination).where(Destination.enabled == True)  # noqa: E712
            )
            destinations = dest_result.scalars().all()
        else:
            dest_result = await session.execute(
                select(Destination).where(Destination.id.in_(request.destination_ids))
            )
            destinations = dest_result.scalars().all()
        
        if not destinations:
            raise HTTPException(status_code=400, detail="No valid destinations found")
        
        # Create ForwardJob entries
        forward_job_ids = []
        for destination in destinations:
            forward_job = ForwardJob(
                study_id=study.id,
                destination_id=destination.id,
                status="pending",
                priority=request.priority,
                max_attempts=3,
            )
            session.add(forward_job)
            forward_job_ids.append(str(forward_job.id))
        
        await session.commit()
        
        return {
            "study_id": str(study_id),
            "forward_job_ids": forward_job_ids,
            "destinations": [d.name for d in destinations],
        }


@router.get("/studies/{study_id}/forward-jobs")
async def get_study_forward_jobs(study_id: UUID = Path(...)):
    """Get forward jobs for a study."""
    async for session in get_db_session():
        result = await session.execute(
            select(ForwardJob)
            .where(ForwardJob.study_id == study_id)
            .options(selectinload(ForwardJob.destination))
            .order_by(ForwardJob.created_at.desc())
        )
        jobs = result.scalars().all()
        
        return [
            {
                "id": str(job.id),
                "destination": job.destination.name if job.destination else None,
                "status": job.status,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message,
            }
            for job in jobs
        ]

