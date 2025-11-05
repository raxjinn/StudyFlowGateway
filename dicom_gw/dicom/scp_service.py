"""Service wrapper for C-STORE SCP to run as a standalone service."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from dicom_gw.dicom.scp import CStoreSCP
from dicom_gw.queue.job_queue import JobQueue
from dicom_gw.config.settings import get_settings

logger = logging.getLogger(__name__)


class CStoreSCPService:
    """Service wrapper for running C-STORE SCP as a standalone service."""
    
    def __init__(self, queue: Optional[JobQueue] = None):
        """Initialize the service.
        
        Args:
            queue: Optional job queue for processing received files
        """
        self.queue = queue or JobQueue()
        self.scp: Optional[CStoreSCP] = None
        self.running = False
    
    def start(self):
        """Start the C-STORE SCP service."""
        settings = get_settings()
        
        self.scp = CStoreSCP(
            ae_title=settings.dicom_ae_title,
            port=settings.dicom_port,
            max_pdu=settings.dicom_max_pdu,
            storage_path=Path(settings.dicom_incoming_path),
            queue=self.queue,
        )
        
        self.scp.start()
        self.running = True
        
        logger.info("C-STORE SCP service started")
    
    def stop(self):
        """Stop the C-STORE SCP service."""
        if self.scp:
            self.scp.stop()
            self.scp = None
        self.running = False
        logger.info("C-STORE SCP service stopped")
    
    def run(self):
        """Run the service until interrupted."""
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the service
        self.start()
        
        try:
            # Keep running
            while self.running:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
            self.stop()


def main():
    """Main entry point for the service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create and run service
    service = CStoreSCPService()
    service.run()


if __name__ == "__main__":
    main()

