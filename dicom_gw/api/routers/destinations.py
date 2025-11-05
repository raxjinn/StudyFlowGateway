"""Destinations endpoints."""

import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field
from datetime import datetime

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import Destination
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


class DestinationCreate(BaseModel):
    """Create destination request model."""
    name: str = Field(..., min_length=1, max_length=255)
    ae_title: str = Field(..., min_length=1, max_length=255)
    host: str
    port: int = Field(..., ge=1, le=65535)
    max_pdu: int = Field(default=16384, ge=128)
    timeout: int = Field(default=30, ge=1)
    connection_timeout: int = Field(default=10, ge=1)
    tls_enabled: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    tls_ca_path: Optional[str] = None
    tls_no_verify: bool = False
    forwarding_rules: Optional[dict] = None
    description: Optional[str] = None


class DestinationUpdate(BaseModel):
    """Update destination request model."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ae_title: Optional[str] = Field(None, min_length=1, max_length=255)
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    max_pdu: Optional[int] = Field(None, ge=128)
    timeout: Optional[int] = Field(None, ge=1)
    connection_timeout: Optional[int] = Field(None, ge=1)
    tls_enabled: Optional[bool] = None
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    tls_ca_path: Optional[str] = None
    tls_no_verify: Optional[bool] = None
    forwarding_rules: Optional[dict] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class DestinationResponse(BaseModel):
    """Destination response model."""
    id: UUID
    name: str
    ae_title: str
    host: str
    port: int
    max_pdu: int
    timeout: int
    connection_timeout: int
    tls_enabled: bool
    tls_cert_path: Optional[str]
    tls_key_path: Optional[str]
    tls_ca_path: Optional[str]
    tls_no_verify: bool
    enabled: bool
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    consecutive_failures: int
    forwarding_rules: Optional[dict]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/destinations", response_model=List[DestinationResponse])
async def list_destinations(
    enabled: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List destinations."""
    async for session in get_db_session():
        query = select(Destination)
        
        if enabled is not None:
            query = query.where(Destination.enabled == enabled)
        
        query = query.order_by(Destination.created_at.desc()).offset(skip).limit(limit)
        
        result = await session.execute(query)
        destinations = result.scalars().all()
        
        return [DestinationResponse.model_validate(dest) for dest in destinations]


@router.get("/destinations/{destination_id}", response_model=DestinationResponse)
async def get_destination(destination_id: UUID = Path(...)):
    """Get destination by ID."""
    async for session in get_db_session():
        result = await session.execute(
            select(Destination).where(Destination.id == destination_id)
        )
        destination = result.scalar_one_or_none()
        
        if not destination:
            raise HTTPException(status_code=404, detail="Destination not found")
        
        return DestinationResponse.model_validate(destination)


@router.post("/destinations", response_model=DestinationResponse, status_code=201)
async def create_destination(destination: DestinationCreate):
    """Create a new destination."""
    async for session in get_db_session():
        # Check if name already exists
        existing = await session.execute(
            select(Destination).where(Destination.name == destination.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Destination name already exists")
        
        new_destination = Destination(
            name=destination.name,
            ae_title=destination.ae_title,
            host=destination.host,
            port=destination.port,
            max_pdu=destination.max_pdu,
            timeout=destination.timeout,
            connection_timeout=destination.connection_timeout,
            tls_enabled=destination.tls_enabled,
            tls_cert_path=destination.tls_cert_path,
            tls_key_path=destination.tls_key_path,
            tls_ca_path=destination.tls_ca_path,
            tls_no_verify=destination.tls_no_verify,
            forwarding_rules=destination.forwarding_rules,
            description=destination.description,
            enabled=True,
        )
        
        session.add(new_destination)
        await session.commit()
        await session.refresh(new_destination)
        
        return DestinationResponse.model_validate(new_destination)


@router.put("/destinations/{destination_id}", response_model=DestinationResponse)
async def update_destination(
    destination_id: UUID = Path(...),
    destination: DestinationUpdate = Body(...),
):
    """Update a destination."""
    async for session in get_db_session():
        result = await session.execute(
            select(Destination).where(Destination.id == destination_id)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Destination not found")
        
        # Update fields
        update_data = destination.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing, key, value)
        
        await session.commit()
        await session.refresh(existing)
        
        return DestinationResponse.model_validate(existing)


@router.delete("/destinations/{destination_id}", status_code=204)
async def delete_destination(destination_id: UUID = Path(...)):
    """Delete a destination."""
    async for session in get_db_session():
        result = await session.execute(
            select(Destination).where(Destination.id == destination_id)
        )
        destination = result.scalar_one_or_none()
        
        if not destination:
            raise HTTPException(status_code=404, detail="Destination not found")
        
        # Check if there are any forward jobs
        from dicom_gw.database.models import ForwardJob
        jobs_result = await session.execute(
            select(ForwardJob).where(ForwardJob.destination_id == destination_id)
        )
        jobs = jobs_result.scalars().all()
        
        if jobs:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete destination with existing forward jobs",
            )
        
        await session.delete(destination)
        await session.commit()
        
        return None

