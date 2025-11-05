"""Integration tests for C-STORE receive (SCP) with byte preservation."""

import pytest
import asyncio
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.io import read_dicom_bytes_sync, verify_byte_equality
from dicom_gw.dicom.scp import CStoreSCP


@pytest.fixture
def test_storage_dir(tmp_path):
    """Create temporary storage directory."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def sample_dicom_file(tmp_path):
    """Create a sample DICOM file for testing."""
    # Create a minimal DICOM dataset
    ds = FileDataset("test.dcm", {}, file_meta=Dataset(), preamble=b"\x00" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9.11"
    ds.SeriesInstanceUID = "1.2.3.4.5.6.7.8.9.12"
    ds.PatientID = "TEST001"
    ds.PatientName = "Test^Patient"
    ds.Modality = "CT"
    ds.StudyDate = "20240101"
    
    # Save with preamble
    dicom_file = tmp_path / "sample.dcm"
    ds.save_as(dicom_file, write_like_original=True)
    
    return dicom_file


@pytest.fixture
def original_bytes(sample_dicom_file):
    """Get original bytes from sample DICOM file."""
    return read_dicom_bytes_sync(sample_dicom_file)


@pytest.mark.integration
@pytest.mark.asyncio
class TestCStoreReceive:
    """Test C-STORE receive with byte preservation."""
    
    async def test_receive_preserves_bytes(self, test_storage_dir, sample_dicom_file):  # noqa: ARG002
        """Test that received DICOM file preserves exact bytes."""
        # Create SCP instance
        scp = CStoreSCP(
            ae_title="TEST_SCP",
            port=0,  # Use random port
            storage_path=str(test_storage_dir),
        )
        
        # Start SCP server
        scp.start()
        
        try:
            # Create SCU client and send file
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            # Read original bytes
            original_data = read_dicom_bytes_sync(sample_dicom_file)
            
            # Connect to SCP and send
            assoc = ae_client.associate("127.0.0.1", scp.port)
            
            if assoc.is_established:
                # Send C-STORE
                status = assoc.send_c_store(sample_dicom_file)
                
                # Check status
                assert status.Status == 0x0000  # Success
                
                assoc.release()
            
            # Wait a bit for file to be written
            await asyncio.sleep(0.5)
            
            # Find the received file
            received_files = list(test_storage_dir.rglob("*.dcm"))
            assert len(received_files) > 0
            
            # Read received file
            received_file = received_files[0]
            received_bytes = read_dicom_bytes_sync(received_file)
            
            # Verify byte-for-byte equality
            assert verify_byte_equality(original_data, received_bytes), \
                "Received file bytes do not match original"
            
            # Verify preamble is preserved
            assert received_bytes[:128] == b'\x00' * 128, \
                "128-byte preamble not preserved"
            
            # Verify DICM prefix
            assert received_bytes[128:132] == b'DICM', \
                "DICM prefix not preserved"
        
        finally:
            scp.stop()
    
    async def test_receive_multiple_files(self, test_storage_dir, tmp_path, original_bytes):  # noqa: ARG002
        """Test receiving multiple DICOM files."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            test_file = tmp_path / f"test_{i}.dcm"
            test_file.write_bytes(original_bytes)
            test_files.append(test_file)
        
        # Create SCP
        scp = CStoreSCP(
            ae_title="TEST_SCP",
            port=0,
            storage_path=str(test_storage_dir),
        )
        
        scp.start()
        
        try:
            # Send all files
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            for test_file in test_files:
                assoc = ae_client.associate("127.0.0.1", scp.port)
                if assoc.is_established:
                    status = assoc.send_c_store(test_file)
                    assert status.Status == 0x0000
                    assoc.release()
                await asyncio.sleep(0.1)
            
            # Wait for processing
            await asyncio.sleep(1.0)
            
            # Verify all files received
            received_files = list(test_storage_dir.rglob("*.dcm"))
            assert len(received_files) >= len(test_files), \
                f"Expected at least {len(test_files)} files, got {len(received_files)}"
        
        finally:
            scp.stop()
    
    async def test_receive_preserves_all_bytes(self, test_storage_dir, sample_dicom_file, original_bytes):  # noqa: ARG002
        """Test that all bytes are preserved, including file size."""
        scp = CStoreSCP(
            ae_title="TEST_SCP",
            port=0,
            storage_path=str(test_storage_dir),
        )
        
        scp.start()
        
        try:
            # Send file
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            assoc = ae_client.associate("127.0.0.1", scp.port)
            if assoc.is_established:
                status = assoc.send_c_store(sample_dicom_file)
                assert status.Status == 0x0000
                assoc.release()
            
            await asyncio.sleep(0.5)
            
            # Find received file
            received_files = list(test_storage_dir.rglob("*.dcm"))
            assert len(received_files) > 0
            
            received_file = received_files[0]
            received_bytes = read_dicom_bytes_sync(received_file)
            
            # Verify exact byte match
            assert len(received_bytes) == len(original_bytes), \
                f"File size mismatch: original={len(original_bytes)}, received={len(received_bytes)}"
            
            assert received_bytes == original_bytes, \
                "Byte content does not match"
        
        finally:
            scp.stop()

