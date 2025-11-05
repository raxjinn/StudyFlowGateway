"""Health check endpoints."""

import logging
from datetime import datetime
from fastapi import APIRouter, Response
from pydantic import BaseModel

from dicom_gw.database.connection import get_db_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_status = "unknown"
    
    try:
        async for session in get_db_session():
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            db_status = "connected"
            break
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "disconnected"
    
    overall_status = "healthy" if db_status == "connected" else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        database=db_status,
    )


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response):
    """Kubernetes readiness probe."""
    try:
        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
            break
        return {"status": "ready"}
    except Exception:
        response.status_code = 503
        return {"status": "not_ready"}

