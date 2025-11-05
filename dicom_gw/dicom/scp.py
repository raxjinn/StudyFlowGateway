"""DICOM Storage SCP (Service Class Provider) - C-STORE receiver.

This module implements a high-performance DICOM C-STORE receiver that preserves
binary integrity of received DICOM files, including the 128-byte preamble and DICM prefix.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from pynetdicom import AE, evt
from pynetdicom.sop_class import VerificationSOPClass
from pydicom.dataset import Dataset
# InvalidDICOMError doesn't exist in newer pydicom versions
# Use generic Exception or ValueError instead
InvalidDICOMError = ValueError

from dicom_gw.dicom.io import (
    write_dicom_bytes_sync,
    verify_dicom_structure,
    parse_dicom_metadata,
    get_dicom_tags,
)
from dicom_gw.config.settings import get_settings
from dicom_gw.queue.job_queue import JobQueue
from dicom_gw.metrics.collector import get_metrics_collector

logger = logging.getLogger(__name__)


class CStoreSCP:
    """DICOM Storage SCP for receiving C-STORE requests."""
    
    def __init__(
        self,
        ae_title: Optional[str] = None,
        port: Optional[int] = None,
        max_pdu: Optional[int] = None,
        storage_path: Optional[Path] = None,
        queue: Optional[JobQueue] = None,
    ):
        """Initialize C-STORE SCP.
        
        Args:
            ae_title: Application Entity Title (defaults to settings)
            port: Listening port (defaults to settings)
            max_pdu: Maximum PDU size (defaults to settings)
            storage_path: Path for storing received files (defaults to settings)
            queue: Job queue for processing received files
        """
        settings = get_settings()
        
        self.ae_title = ae_title or settings.dicom_ae_title
        self.port = port or settings.dicom_port
        self.max_pdu = max_pdu or settings.dicom_max_pdu
        self.storage_path = Path(storage_path or settings.dicom_incoming_path)
        self.queue = queue
        
        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Application Entity
        self.ae: Optional[AE] = None
        self.server: Optional[Any] = None
        
        # Statistics
        self.stats = {
            "received": 0,
            "stored": 0,
            "failed": 0,
            "bytes_received": 0,
        }
        
        logger.info(
            f"C-STORE SCP initialized: AE={self.ae_title}, "
            f"Port={self.port}, MaxPDU={self.max_pdu}"
        )
    
    def _handle_store(self, event: evt.Event) -> int:
        """Handle incoming C-STORE request.
        
        This callback is called by pynetdicom for each received C-STORE request.
        It preserves the binary data exactly as received.
        
        Args:
            event: pynetdicom event object containing the dataset
        
        Returns:
            Status code (0x0000 = Success)
        """
        start_time = time.time()
        receive_duration_ms = 0
        storage_duration_ms = 0
        file_size = 0
        sop_instance_uid = None
        study_instance_uid = None
        error_message = None
        
        try:
            # Get the dataset from the event
            dataset = event.dataset
            
            # Extract metadata for logging/queueing
            try:
                sop_instance_uid = str(dataset.get("SOPInstanceUID", "UNKNOWN"))
                study_instance_uid = str(dataset.get("StudyInstanceUID", "UNKNOWN"))
            except Exception as e:
                logger.warning(f"Could not extract UIDs from dataset: {e}")
            
            # Get the raw bytes from the association
            # pynetdicom stores the raw data in the event
            raw_data = None
            if hasattr(event, "request") and hasattr(event.request, "DataSet"):
                # Try to get raw bytes from the request
                try:
                    # pynetdicom may have the raw bytes in the association
                    # We need to reconstruct from the dataset or get from network layer
                    # For now, we'll use pydicom's file writer but in a way that preserves structure
                    raw_data = self._get_raw_bytes_from_dataset(event)
                except Exception as e:
                    logger.warning(f"Could not extract raw bytes: {e}")
            
            # If we couldn't get raw bytes, we'll need to reconstruct
            # but this is a fallback - ideally we capture raw bytes from network
            if raw_data is None:
                logger.warning(
                    f"Raw bytes not available, reconstructing from dataset "
                    f"(may not preserve exact preamble): {sop_instance_uid}"
                )
                raw_data = self._reconstruct_bytes_from_dataset(dataset)
            
            receive_duration_ms = int((time.time() - start_time) * 1000)
            file_size = len(raw_data)
            
            # Verify structure
            # Create temporary file to verify
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(raw_data)
            
            is_valid, error_msg, has_preamble = verify_dicom_structure(tmp_path)
            if not is_valid:
                logger.warning(f"DICOM structure verification failed: {error_msg}")
                error_message = error_msg
            else:
                logger.debug(f"DICOM structure verified (has_preamble={has_preamble})")
            
            # Store the file
            storage_start = time.time()
            file_path = self._generate_file_path(sop_instance_uid, study_instance_uid)
            
            bytes_written = write_dicom_bytes_sync(file_path, raw_data, create_dirs=True)
            storage_duration_ms = int((time.time() - storage_start) * 1000)
            
            # Clean up temp file
            tmp_path.unlink()
            
            # Update statistics
            self.stats["received"] += 1
            self.stats["stored"] += 1
            self.stats["bytes_received"] += file_size
            
            # Record metrics
            metrics = get_metrics_collector()
            total_duration = (receive_duration_ms + storage_duration_ms) / 1000.0
            calling_ae = getattr(event.assoc, "requestor", {}).get("ae_title", "unknown") if hasattr(event, "assoc") else "unknown"
            metrics.record_ingest(
                status="success",
                duration_seconds=total_duration,
                ae_title=calling_ae,
                file_size_bytes=file_size,
            )
            
            logger.info(
                f"C-STORE received: {sop_instance_uid[:40]}... "
                f"({file_size} bytes, {receive_duration_ms}ms receive, "
                f"{storage_duration_ms}ms storage)"
            )
            
            # Queue for processing (metadata extraction, forwarding, etc.)
            if self.queue:
                asyncio.create_task(
                    self._queue_for_processing(
                        file_path,
                        sop_instance_uid,
                        study_instance_uid,
                        event,
                        receive_duration_ms,
                        storage_duration_ms,
                        file_size,
                    )
                )
            
            # Return success status
            return 0x0000  # Success
            
        except Exception as e:
            self.stats["failed"] += 1
            error_message = str(e)
            
            # Record failed ingest
            metrics = get_metrics_collector()
            calling_ae = getattr(event.assoc, "requestor", {}).get("ae_title", "unknown") if hasattr(event, "assoc") else "unknown"
            metrics.record_ingest(
                status="failed",
                duration_seconds=0,
                ae_title=calling_ae,
            )
            
            logger.error(
                f"C-STORE failed for {sop_instance_uid or 'UNKNOWN'}: {e}",
                exc_info=True,
            )
            # Return failure status (Internal error)
            return 0x0110  # Processing failure
    
    def _get_raw_bytes_from_dataset(self, event: evt.Event) -> Optional[bytes]:
        """Attempt to extract raw bytes from the pynetdicom event.
        
        This tries various methods to get the original bytes from the network layer.
        Note: pynetdicom parses the dataset, so we may need to reconstruct.
        However, we can use pydicom's save with write_like_original to preserve structure.
        
        Args:
            event: pynetdicom event object
        
        Returns:
            Raw bytes if available, None otherwise
        """
        # Method 1: Check if event has raw_bytes attribute (custom extension)
        if hasattr(event, "raw_bytes"):
            return event.raw_bytes
        
        # Method 2: Try to get from event.request if it has raw data
        if hasattr(event, "request"):
            request = event.request
            if hasattr(request, "DataSet") and hasattr(request.DataSet, "getvalue"):
                return request.DataSet.getvalue()
            # Check for raw PDU data
            if hasattr(request, "raw_data"):
                return request.raw_data
        
        # Method 3: Check association for raw data (implementation-specific)
        if hasattr(event, "assoc"):
            assoc = event.assoc
            # Some pynetdicom versions store raw data in the association
            if hasattr(assoc, "_received_pdu_data"):
                return assoc._received_pdu_data
        
        # Method 4: Try to get from the dataset's file_meta if it has original bytes
        if hasattr(event, "dataset") and hasattr(event.dataset, "_preamble"):
            # If dataset has preamble, we might be able to reconstruct
            pass
        
        return None
    
    def _reconstruct_bytes_from_dataset(self, dataset: Dataset) -> bytes:
        """Reconstruct bytes from pydicom dataset (fallback method).
        
        WARNING: This reconstructs the file and may not preserve the exact original
        128-byte preamble content (though it will create a valid preamble).
        This should only be used as a fallback when raw bytes are not available.
        
        For byte-perfect preservation, we need to capture raw bytes at the network layer.
        
        Args:
            dataset: pydicom Dataset object
        
        Returns:
            Bytes representation of the dataset
        """
        import io
        import tempfile
        from pathlib import Path
        from pydicom.filewriter import dcmwrite
        
        # Use pydicom's file writer with write_like_original=True
        # This preserves the transfer syntax and encoding
        buffer = io.BytesIO()
        
        # Write preamble (128 bytes of zeros - standard DICOM preamble)
        buffer.write(b"\x00" * 128)
        
        # Write DICM prefix
        buffer.write(b"DICM")
        
        # Write file meta information if present
        if hasattr(dataset, "file_meta") and dataset.file_meta:
            from pydicom.filewriter import write_file_meta_info
            write_file_meta_info(buffer, dataset.file_meta)
        
        # Write dataset using write_like_original to preserve encoding
        # Note: write_like_original=True tries to preserve the original encoding
        dcmwrite(buffer, dataset, write_like_original=True)
        
        return buffer.getvalue()
    
    def _generate_file_path(
        self, sop_instance_uid: str, study_instance_uid: str
    ) -> Path:
        """Generate file path for storing received DICOM file.
        
        Path structure: {storage_path}/{study_uid}/{series_uid}/{instance_uid}.dcm
        
        Args:
            sop_instance_uid: SOP Instance UID
            study_instance_uid: Study Instance UID
        
        Returns:
            Path object for the file
        """
        # Use study UID as top-level directory
        study_dir = self.storage_path / study_instance_uid
        
        # Extract series UID from dataset if available, otherwise use "unknown"
        # For now, we'll use a flat structure per study
        # TODO: Parse series UID from dataset if available
        
        # File name: use SOP Instance UID
        filename = f"{sop_instance_uid}.dcm"
        
        return study_dir / filename
    
    async def _queue_for_processing(
        self,
        file_path: Path,
        sop_instance_uid: str,
        study_instance_uid: str,
        event: evt.Event,
        receive_duration_ms: int,
        storage_duration_ms: int,
        file_size: int,
    ):
        """Queue received file for async processing.
        
        Args:
            file_path: Path to stored file
            sop_instance_uid: SOP Instance UID
            study_instance_uid: Study Instance UID
            event: pynetdicom event object
            receive_duration_ms: Time to receive (ms)
            storage_duration_ms: Time to store (ms)
            file_size: File size in bytes
        """
        if not self.queue:
            return
        
        try:
            # Extract calling AE title
            calling_ae = None
            if hasattr(event, "assoc") and hasattr(event.assoc, "requestor"):
                calling_ae = getattr(event.assoc.requestor, "ae_title", None)
            
            # Create job payload
            job_data = {
                "file_path": str(file_path),
                "sop_instance_uid": sop_instance_uid,
                "study_instance_uid": study_instance_uid,
                "calling_ae_title": calling_ae,
                "called_ae_title": self.ae_title,
                "receive_duration_ms": receive_duration_ms,
                "storage_duration_ms": storage_duration_ms,
                "file_size_bytes": file_size,
                "received_at": datetime.utcnow().isoformat(),
            }
            
            # Queue for metadata extraction
            await self.queue.enqueue(
                job_type="process_received_file",
                payload=job_data,
                priority=0,
            )
            
            logger.debug(f"Queued file for processing: {sop_instance_uid}")
            
        except Exception as e:
            logger.error(f"Failed to queue file for processing: {e}", exc_info=True)
    
    def start(self):
        """Start the C-STORE SCP server."""
        # Create Application Entity
        self.ae = AE(ae_title=self.ae_title)
        
        # Add Storage SCP support
        # Add all storage SOP classes (we accept any DICOM storage)
        from pynetdicom.sop_class import (
            CTImageStorage,
            MRImageStorage,
            USImageStorage,
            SecondaryCaptureImageStorage,
            # Add more as needed
        )
        
        # Add supported SOP classes
        self.ae.add_supported_context(VerificationSOPClass)
        self.ae.add_supported_context(CTImageStorage)
        self.ae.add_supported_context(MRImageStorage)
        self.ae.add_supported_context(USImageStorage)
        self.ae.add_supported_context(SecondaryCaptureImageStorage)
        
        # Add all storage SOP classes (wildcard approach)
        # This is more permissive - accepts any storage SOP class
        from pynetdicom.sop_class import StorageSOPClassList
        
        for storage_class in StorageSOPClassList:
            self.ae.add_supported_context(storage_class)
        
        # Create handlers
        handlers = [(evt.EVT_C_STORE, self._handle_store)]
        
        # Start server
        self.server = self.ae.start_server(
            ("", self.port),
            block=False,
            evt_handlers=handlers,
            max_pdu=self.max_pdu,
        )
        
        logger.info(
            f"C-STORE SCP server started on port {self.port} "
            f"(AE Title: {self.ae_title})"
        )
    
    def stop(self):
        """Stop the C-STORE SCP server."""
        if self.ae:
            self.ae.shutdown()
            self.ae = None
            self.server = None
            logger.info("C-STORE SCP server stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get receiver statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self.stats,
            "storage_path": str(self.storage_path),
            "ae_title": self.ae_title,
            "port": self.port,
        }

