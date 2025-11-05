"""Audit log endpoints."""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import AuditLog
from dicom_gw.security.rbac import Permission
from dicom_gw.api.dependencies import require_permission
from sqlalchemy import select, and_, func

logger = logging.getLogger(__name__)

router = APIRouter()

# Require admin or audit view permission
RequireAuditView = require_permission(Permission.VIEW_AUDIT)


class AuditLogResponse(BaseModel):
    """Audit log response model."""
    id: str
    user_id: Optional[str]
    username: Optional[str]
    ip_address: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    status: str
    error_message: Optional[str]
    metadata: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/audit", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user=Depends(RequireAuditView),  # pylint: disable=unused-argument
):
    """List audit logs with filtering.
    
    Only users with VIEW_AUDIT permission can access audit logs.
    """
    async for session in get_db_session():
        query = select(AuditLog)
        
        # Apply filters
        filters = []
        
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if username:
            filters.append(AuditLog.username == username)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if resource_id:
            filters.append(AuditLog.resource_id == resource_id)
        if status:
            filters.append(AuditLog.status == status)
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.where(and_(*filters))
        
        # Order by most recent first
        query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        
        result = await session.execute(query)
        logs = result.scalars().all()
        
        return [AuditLogResponse.model_validate(log) for log in logs]


@router.get("/audit/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: str,
    current_user=Depends(RequireAuditView),  # pylint: disable=unused-argument
):
    """Get a specific audit log entry by ID."""
    async for session in get_db_session():
        result = await session.execute(
            select(AuditLog).where(AuditLog.id == audit_id)
        )
        log = result.scalar_one_or_none()
        
        if not log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        
        return AuditLogResponse.model_validate(log)


@router.get("/audit/stats/summary")
async def get_audit_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user=Depends(RequireAuditView),  # pylint: disable=unused-argument
):
    """Get audit log statistics summary."""
    
    async for session in get_db_session():
        query = select(
            AuditLog.action,
            AuditLog.status,
            func.count(AuditLog.id).label("count"),
        )
        
        filters = []
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.group_by(AuditLog.action, AuditLog.status)
        
        result = await session.execute(query)
        stats = result.all()
        
        # Format results
        summary = {}
        for action, status, count in stats:
            if action not in summary:
                summary[action] = {"success": 0, "failure": 0, "denied": 0}
            summary[action][status] = count
        
        return {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "summary": summary,
        }

