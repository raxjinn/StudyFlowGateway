"""Middleware for automatic metrics collection."""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
        
        Returns:
            Response object
        """
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration (for future HTTP metrics)
        _duration = time.time() - start_time
        
        # Record metrics (for future HTTP metrics)
        # _collector = get_metrics_collector()
        # For now, we'll focus on application-specific metrics
        
        return response

