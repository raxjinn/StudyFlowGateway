"""FastAPI application main module."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dicom_gw.config.settings import get_settings
from dicom_gw.api.routers import health, metrics, studies, destinations, queues, config, auth, audit
from dicom_gw.database.connection import close_db
from dicom_gw.database.pool import init_asyncpg_pool, close_asyncpg_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting DICOM Gateway API")
    
    # Initialize database connections
    await init_asyncpg_pool()
    # await init_db()  # Uncomment if needed for auto-create tables
    
    yield
    
    # Shutdown
    logger.info("Shutting down DICOM Gateway API")
    await close_asyncpg_pool()
    await close_db()


# Create FastAPI app
settings = get_settings()

app = FastAPI(
    title="DICOM Gateway API",
    description="REST API for DICOM Gateway - Receiving and Forwarding Medical Imaging Studies",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_debug else None,
    redoc_url="/api/redoc" if settings.app_debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.app_debug else "An error occurred",
        },
    )


# Include routers
app.include_router(auth.router, prefix=settings.api_prefix, tags=["Authentication"])
app.include_router(audit.router, prefix=settings.api_prefix, tags=["Audit"])
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(metrics.router, prefix=settings.api_prefix, tags=["Metrics"])
app.include_router(studies.router, prefix=settings.api_prefix, tags=["Studies"])
app.include_router(destinations.router, prefix=settings.api_prefix, tags=["Destinations"])
app.include_router(queues.router, prefix=settings.api_prefix, tags=["Queues"])
app.include_router(config.router, prefix=settings.api_prefix, tags=["Config"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "DICOM Gateway API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/api/docs" if settings.app_debug else "disabled",
    }


def main():
    """Main entry point for running the API server."""
    import uvicorn
    
    uvicorn.run(
        "dicom_gw.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

