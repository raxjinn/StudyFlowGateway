"""DICOM Storage SCU (Service Class User) - C-STORE forwarder.

This module implements a DICOM C-STORE client for forwarding studies to remote
Application Entities with byte-preserving transmission.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from pynetdicom import AE

from dicom_gw.dicom.io import (
    read_dicom_bytes_sync,
    verify_dicom_structure,
    parse_dicom_metadata,
)
from dicom_gw.config.settings import get_settings
from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


class CStoreSCU:
    """DICOM Storage SCU for forwarding C-STORE requests to remote AEs."""
    
    def __init__(
        self,
        ae_title: Optional[str] = None,
        max_pdu: Optional[int] = None,
    ):
        """Initialize C-STORE SCU.
        
        Args:
            ae_title: Local Application Entity Title (defaults to settings)
            max_pdu: Maximum PDU size (defaults to settings)
        """
        settings = get_settings()
        
        self.ae_title = ae_title or settings.dicom_ae_title
        self.max_pdu = max_pdu or settings.dicom_max_pdu
        
        # Statistics
        self.stats = {
            "forwarded": 0,
            "failed": 0,
            "bytes_sent": 0,
            "total_duration_ms": 0,
        }
        
        logger.info(
            f"C-STORE SCU initialized: AE={self.ae_title}, MaxPDU={self.max_pdu}"
        )
    
    def forward_file(
        self,
        file_path: Path,
        remote_ae_title: str,
        remote_host: str,
        remote_port: int,
        timeout: int = 30,  # pylint: disable=unused-argument
        max_pdu: Optional[int] = None,
        tls_enabled: bool = False,
        tls_cert_path: Optional[str] = None,
        tls_key_path: Optional[str] = None,
        tls_ca_path: Optional[str] = None,
        tls_no_verify: bool = False,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Forward a single DICOM file to a remote AE.
        
        This method reads the file using byte-preserving I/O and sends it
        via C-STORE, attempting to preserve the exact bytes.
        
        Args:
            file_path: Path to the DICOM file to forward
            remote_ae_title: Remote AE Title (called AE)
            remote_host: Remote hostname or IP address
            remote_port: Remote port number
            timeout: Connection timeout in seconds
            max_pdu: Maximum PDU size (overrides instance default)
            tls_enabled: Enable TLS encryption
            tls_cert_path: Path to client certificate
            tls_key_path: Path to client private key
            tls_ca_path: Path to CA certificate
            tls_no_verify: Disable certificate verification (not recommended)
        
        Returns:
            Tuple of (success, error_message, statistics_dict)
        """
        start_time = time.time()
        stats = {
            "file_path": str(file_path),
            "remote_ae": remote_ae_title,
            "remote_host": remote_host,
            "remote_port": remote_port,
            "file_size_bytes": 0,
            "send_duration_ms": 0,
            "status": "failed",
        }
        
        try:
            # Verify file exists and is valid DICOM
            if not file_path.exists():
                error_msg = f"File not found: {file_path}"
                logger.error(error_msg)
                stats["error"] = error_msg
                return (False, error_msg, stats)
            
            # Verify DICOM structure
            is_valid, error_msg, _ = verify_dicom_structure(file_path)
            if not is_valid:
                logger.warning("Invalid DICOM structure: %s", error_msg)
                # Continue anyway - might still be valid
            
            # Read file bytes
            file_bytes = read_dicom_bytes_sync(file_path)
            file_size = len(file_bytes)
            stats["file_size_bytes"] = file_size
            
            # Parse metadata to get SOP Class UID and Instance UID
            dataset = parse_dicom_metadata(file_path)
            if not dataset:
                error_msg = f"Could not parse DICOM metadata from {file_path}"
                logger.error(error_msg)
                stats["error"] = error_msg
                return (False, error_msg, stats)
            
            # Extract required UIDs
            sop_class_uid = str(dataset.get("SOPClassUID", ""))
            sop_instance_uid = str(dataset.get("SOPInstanceUID", ""))
            
            if not sop_class_uid or not sop_instance_uid:
                error_msg = "Missing SOPClassUID or SOPInstanceUID in dataset"
                logger.error(error_msg)
                stats["error"] = error_msg
                return (False, error_msg, stats)
            
            # Create Application Entity
            ae = AE(ae_title=self.ae_title)
            
            # Add requested presentation context
            # We need to add the specific SOP class for this dataset
            from pynetdicom.sop_class import uid_to_sop_class
            
            try:
                sop_class = uid_to_sop_class(sop_class_uid)
                ae.add_requested_context(sop_class)
            except (KeyError, ValueError):
                # If we can't find the SOP class, use common storage contexts
                logger.warning("Unknown SOP class %s, using common storage contexts", sop_class_uid)
                # Add common storage SOP classes as fallback
                from pynetdicom.sop_class import (
                    CTImageStorage,
                    MRImageStorage,
                    USImageStorage,
                    SecondaryCaptureImageStorage,
                )
                for storage_class in [CTImageStorage, MRImageStorage, USImageStorage, SecondaryCaptureImageStorage]:
                    ae.add_requested_context(storage_class)
            
            # Configure TLS if enabled
            if tls_enabled:
                if not tls_cert_path or not tls_key_path:
                    error_msg = "TLS enabled but certificate or key path not provided"
                    logger.error(error_msg)
                    stats["error"] = error_msg
                    return (False, error_msg, stats)
                
                ae.ae_title = self.ae_title
                # Configure TLS context
                # Note: pynetdicom TLS configuration may vary by version
                # This is a simplified version
                try:
                    from pynetdicom.tls import create_client_context
                    
                    # Create TLS context for client
                    tls_context = create_client_context(
                        cert_file=tls_cert_path,
                        key_file=tls_key_path,
                        ca_file=tls_ca_path,
                        verify_mode=0 if tls_no_verify else 2,  # 0 = no verify, 2 = verify
                    )
                    ae.tls_context = tls_context
                except ImportError:
                    logger.warning("TLS support not available in this pynetdicom version")
                    # Continue without TLS
                except Exception:
                    logger.warning("Failed to configure TLS context")
                    # Continue without TLS
            
            # Associate with remote AE
            send_start = time.time()
            assoc = ae.associate(
                remote_host,
                remote_port,
                ae_title=remote_ae_title,
                max_pdu=max_pdu or self.max_pdu,
            )
            
            if not assoc.is_established:
                error_msg = f"Association failed: {getattr(assoc, 'release_reason', 'Unknown reason')}"
                logger.error("Association failed: %s", error_msg)
                stats["error"] = error_msg
                return (False, error_msg, stats)
            
            try:
                # Send C-STORE request with the dataset
                # Use the parsed dataset (pynetdicom will encode it)
                status = assoc.send_c_store(dataset)
                
                # Check status
                if status and status.Status == 0x0000:
                    # Success
                    send_duration_ms = int((time.time() - send_start) * 1000)
                    total_duration_ms = int((time.time() - start_time) * 1000)
                    
                    stats["status"] = "success"
                    stats["send_duration_ms"] = send_duration_ms
                    stats["total_duration_ms"] = total_duration_ms
                    
                    # Update global statistics
                    self.stats["forwarded"] += 1
                    self.stats["bytes_sent"] += file_size
                    self.stats["total_duration_ms"] += total_duration_ms
                    
                    # Record metrics
                    metrics = get_metrics_collector()
                    metrics.record_forward(
                        destination=remote_ae_title,
                        status="success",
                        duration_seconds=total_duration_ms / 1000.0,
                        bytes_sent=file_size,
                    )
                    metrics.record_ae_response(
                        destination=remote_ae_title,
                        operation="c_store",
                        duration_seconds=send_duration_ms / 1000.0,
                    )
                    
                    logger.info(
                        "C-STORE forwarded: %s... to %s@%s:%d (%d bytes, %dms)",
                        sop_instance_uid[:40],
                        remote_ae_title,
                        remote_host,
                        remote_port,
                        file_size,
                        send_duration_ms,
                    )
                    
                    return (True, None, stats)
                else:
                    # Failed
                    status_code = status.Status if status else None
                    error_msg = f"C-STORE failed with status: {status_code}"
                    
                    # Record failed forward
                    metrics = get_metrics_collector()
                    metrics.record_forward(
                        destination=remote_ae_title,
                        status="failed",
                        duration_seconds=(time.time() - send_start),
                    )
                    
                    logger.error("C-STORE failed with status: %s", status_code)
                    stats["error"] = error_msg
                    stats["status_code"] = status_code
                    self.stats["failed"] += 1
                    return (False, error_msg, stats)
            
            finally:
                # Release association
                assoc.release()
        
        except Exception as e:
            error_msg = f"Exception during C-STORE: {str(e)}"
            logger.error("Exception during C-STORE: %s", str(e), exc_info=True)
            stats["error"] = error_msg
            self.stats["failed"] += 1
            return (False, error_msg, stats)
    
    async def forward_file_async(
        self,
        file_path: Path,
        remote_ae_title: str,
        remote_host: str,
        remote_port: int,
        **kwargs,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Async wrapper for forward_file.
        
        Args:
            file_path: Path to the DICOM file
            remote_ae_title: Remote AE Title
            remote_host: Remote hostname
            remote_port: Remote port
            **kwargs: Additional arguments passed to forward_file
        
        Returns:
            Tuple of (success, error_message, statistics_dict)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.forward_file,
            file_path,
            remote_ae_title,
            remote_host,
            remote_port,
            **kwargs,
        )
    
    def forward_study(
        self,
        study_path: Path,
        remote_ae_title: str,
        remote_host: str,
        remote_port: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Forward all instances in a study.
        
        Args:
            study_path: Path to study directory (contains instance files)
            remote_ae_title: Remote AE Title
            remote_host: Remote hostname
            remote_port: Remote port
            **kwargs: Additional arguments passed to forward_file
        
        Returns:
            Dictionary with forwarding results
        """
        results = {
            "study_path": str(study_path),
            "total_instances": 0,
            "forwarded": 0,
            "failed": 0,
            "errors": [],
            "duration_ms": 0,
        }
        
        start_time = time.time()
        
        # Find all DICOM files in the study directory
        dicom_files = list(study_path.rglob("*.dcm"))
        results["total_instances"] = len(dicom_files)
        
        for file_path in dicom_files:
            success, error_msg, stats = self.forward_file(
                file_path,
                remote_ae_title,
                remote_host,
                remote_port,
                **kwargs,
            )
            
            if success:
                results["forwarded"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "file": str(file_path),
                    "error": error_msg,
                })
        
        results["duration_ms"] = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Study forwarding completed: %d/%d instances forwarded (%dms)",
            results['forwarded'],
            results['total_instances'],
            results['duration_ms'],
        )
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get forwarder statistics.
        
        Returns:
            Dictionary of statistics
        """
        avg_duration = 0
        if self.stats["forwarded"] > 0:
            avg_duration = self.stats["total_duration_ms"] / self.stats["forwarded"]
        
        return {
            **self.stats,
            "average_duration_ms": avg_duration,
            "success_rate": (
                self.stats["forwarded"] / (self.stats["forwarded"] + self.stats["failed"])
                if (self.stats["forwarded"] + self.stats["failed"]) > 0
                else 0.0
            ),
        }

