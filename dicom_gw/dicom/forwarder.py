"""High-level forwarder with retry logic and destination management."""

import asyncio
import logging
import math
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from dicom_gw.dicom.scu import CStoreSCU
from dicom_gw.database.models import Destination, ForwardJob
from dicom_gw.database.connection import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


@dataclass
class ForwardResult:
    """Result of a forwarding operation."""
    success: bool
    error_message: Optional[str]
    attempt: int
    duration_ms: int
    file_path: str
    destination_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class Forwarder:
    """High-level forwarder with retry logic and destination management."""
    
    def __init__(self, scu: Optional[CStoreSCU] = None):
        """Initialize forwarder.
        
        Args:
            scu: Optional CStoreSCU instance (creates new one if None)
        """
        self.scu = scu or CStoreSCU()
        self.default_max_attempts = 3
        self.default_backoff_base = 2.0  # Exponential backoff base
    
    async def forward_file_with_retry(
        self,
        file_path: Path,
        destination_id: str,
        max_attempts: Optional[int] = None,
        backoff_base: float = 2.0,
    ) -> ForwardResult:
        """Forward a file with automatic retry logic.
        
        Args:
            file_path: Path to DICOM file
            destination_id: UUID of destination from database
            max_attempts: Maximum retry attempts (defaults to instance default)
            backoff_base: Exponential backoff base (defaults to 2.0)
        
        Returns:
            ForwardResult object
        """
        max_attempts = max_attempts or self.default_max_attempts
        start_time = datetime.utcnow()
        
        # Get destination from database
        async for session in get_db_session():
            result = await session.execute(
                select(Destination).where(Destination.id == destination_id)
            )
            destination = result.scalar_one_or_none()
            
            if not destination:
                return ForwardResult(
                    success=False,
                    error_message=f"Destination not found: {destination_id}",
                    attempt=0,
                    duration_ms=0,
                    file_path=str(file_path),
                    destination_id=destination_id,
                )
            
            if not destination.enabled:
                return ForwardResult(
                    success=False,
                    error_message="Destination is disabled",
                    attempt=0,
                    duration_ms=0,
                    file_path=str(file_path),
                    destination_id=destination_id,
                )
            break  # Exit after first iteration
        
        # Forward with retry
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                # Calculate exponential backoff delay (except for first attempt)
                if attempt > 1:
                    delay_seconds = math.pow(backoff_base, attempt - 2)
                    await asyncio.sleep(delay_seconds)
                
                # Forward file
                success, error_msg, stats = await self.scu.forward_file_async(
                    file_path,
                    remote_ae_title=destination.ae_title,
                    remote_host=destination.host,
                    remote_port=destination.port,
                    timeout=destination.timeout,
                    max_pdu=destination.max_pdu,
                    tls_enabled=destination.tls_enabled,
                    tls_cert_path=destination.tls_cert_path,
                    tls_key_path=destination.tls_key_path,
                    tls_ca_path=destination.tls_ca_path,
                    tls_no_verify=destination.tls_no_verify,
                )
                
                if success:
                    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    
                    # Update destination stats on success
                    async for session in get_db_session():
                        result = await session.execute(
                            select(Destination).where(Destination.id == destination_id)
                        )
                        destination = result.scalar_one_or_none()
                        if destination:
                            destination.last_success_at = datetime.utcnow()
                            destination.consecutive_failures = 0
                            await session.commit()
                        break
                    
                    return ForwardResult(
                        success=True,
                        error_message=None,
                        attempt=attempt,
                        duration_ms=duration_ms,
                        file_path=str(file_path),
                        destination_id=destination_id,
                        stats=stats,
                    )
                else:
                    last_error = error_msg
                    logger.warning(
                        f"Forward attempt {attempt}/{max_attempts} failed: {error_msg}"
                    )
            
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Exception during forward attempt {attempt}/{max_attempts}: {e}",
                    exc_info=True,
                )
        
        # All attempts failed
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Update destination stats on failure
        async for session in get_db_session():
            result = await session.execute(
                select(Destination).where(Destination.id == destination_id)
            )
            destination = result.scalar_one_or_none()
            if destination:
                destination.last_failure_at = datetime.utcnow()
                destination.consecutive_failures += 1
                await session.commit()
            break
        
        return ForwardResult(
            success=False,
            error_message=f"All {max_attempts} attempts failed. Last error: {last_error}",
            attempt=max_attempts,
            duration_ms=duration_ms,
            file_path=str(file_path),
            destination_id=destination_id,
        )
    
    async def forward_study_to_destination(
        self,
        study_instance_uid: str,
        destination_id: str,
        storage_path: Path,
        max_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Forward all instances in a study to a destination.
        
        Args:
            study_instance_uid: Study Instance UID
            destination_id: UUID of destination
            storage_path: Base storage path (study files are in {storage_path}/{study_uid}/)
            max_attempts: Maximum retry attempts per instance
        
        Returns:
            Dictionary with forwarding results
        """
        study_path = storage_path / study_instance_uid
        
        if not study_path.exists():
            return {
                "success": False,
                "error": f"Study path not found: {study_path}",
                "instances_forwarded": 0,
                "instances_failed": 0,
            }
        
        # Find all DICOM files
        dicom_files = list(study_path.rglob("*.dcm"))
        
        results = {
            "study_instance_uid": study_instance_uid,
            "destination_id": destination_id,
            "total_instances": len(dicom_files),
            "instances_forwarded": 0,
            "instances_failed": 0,
            "errors": [],
        }
        
        # Forward each file
        for file_path in dicom_files:
            result = await self.forward_file_with_retry(
                file_path,
                destination_id,
                max_attempts=max_attempts,
            )
            
            if result.success:
                results["instances_forwarded"] += 1
            else:
                results["instances_failed"] += 1
                results["errors"].append({
                    "file": str(file_path),
                    "error": result.error_message,
                    "attempts": result.attempt,
                })
        
        results["success"] = results["instances_failed"] == 0
        
        logger.info(
            f"Study forwarding completed: {study_instance_uid} -> {destination_id}: "
            f"{results['instances_forwarded']}/{results['total_instances']} instances forwarded"
        )
        
        return results
    
    async def forward_job(
        self,
        job: ForwardJob,
        storage_path: Path,
    ) -> ForwardResult:
        """Forward a job from the forward_jobs table.
        
        Args:
            job: ForwardJob database object
            storage_path: Base storage path for finding study files
        
        Returns:
            ForwardResult object
        """
        # Get study instance UID
        async for session in get_db_session():
            result = await session.execute(
                select(ForwardJob).where(ForwardJob.id == job.id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return ForwardResult(
                    success=False,
                    error_message="Job not found",
                    attempt=0,
                    duration_ms=0,
                    file_path="",
                )
            
            # Get study
            study = job.study
            study_instance_uid = study.study_instance_uid
            break
        
        # Forward study
        results = await self.forward_study_to_destination(
            study_instance_uid,
            str(job.destination_id),
            storage_path,
            max_attempts=job.max_attempts,
        )
        
        # Determine overall success
        success = results.get("success", False)
        error_msg = None if success else f"{results.get('instances_failed', 0)} instances failed"
        
        return ForwardResult(
            success=success,
            error_message=error_msg,
            attempt=job.attempts + 1,
            duration_ms=0,  # Could track from results
            file_path=str(storage_path / study_instance_uid),
            destination_id=str(job.destination_id),
            stats=results,
        )

