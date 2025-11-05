"""Integration tests for C-STORE forward (SCU) with byte preservation."""

import pytest
import time
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE, evt
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.io import read_dicom_bytes_sync, verify_byte_equality
from dicom_gw.dicom.scu import CStoreSCU


@pytest.fixture
def sample_dicom_file(tmp_path):
    """Create a sample DICOM file for testing."""
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
    ds.Modality = "CT"
    
    dicom_file = tmp_path / "sample.dcm"
    ds.save_as(dicom_file, write_like_original=True)
    
    return dicom_file


@pytest.fixture
def mock_scp_server(tmp_path):
    """Create a mock SCP server to receive forwarded files."""
    received_files = []
    
    def handle_store(event):
        """Handle C-STORE request."""
        # Save received dataset
        received_file = tmp_path / f"received_{len(received_files)}.dcm"
        event.dataset.save_as(received_file, write_like_original=True)
        received_files.append(received_file)
        return 0x0000  # Success
    
    handlers = [(evt.EVT_C_STORE, handle_store)]
    
    ae = AE()
    ae.add_supported_context(CTImageStorage)
    
    # Start server
    server = ae.start_server(("127.0.0.1", 0), evt_handlers=handlers, block=False)
    
    # Get the port
    port = server.socket.getsockname()[1]
    
    yield {
        "server": server,
        "port": port,
        "received_files": received_files,
    }
    
    # Cleanup
    server.shutdown()


@pytest.mark.integration
class TestCStoreForward:
    """Test C-STORE forward with byte preservation."""
    
    def test_forward_preserves_bytes(self, sample_dicom_file, mock_scp_server):  # noqa: ARG002
        """Test that forwarded DICOM file preserves exact bytes."""
        # Get original bytes
        original_bytes = read_dicom_bytes_sync(sample_dicom_file)
        
        # Create SCU client
        scu = CStoreSCU()
        
        # Forward file
        success, error, _stats = scu.forward_file(
            file_path=sample_dicom_file,
            remote_ae_title="TEST_SCP",
            remote_host="127.0.0.1",
            remote_port=mock_scp_server["port"],
        )
        
        # Wait for file to be received
        time.sleep(0.5)
        
        # Check success
        assert success is True, f"Forward failed: {error}"
        
        # Check that file was received
        received_files = mock_scp_server["received_files"]
        assert len(received_files) > 0, "No files received by mock SCP"
        
        # Read received file
        received_file = received_files[0]
        received_bytes = read_dicom_bytes_sync(received_file)
        
        # Verify byte-for-byte equality
        assert verify_byte_equality(original_bytes, received_bytes), \
            "Forwarded file bytes do not match original"
        
        # Verify preamble
        assert received_bytes[:128] == b'\x00' * 128, \
            "128-byte preamble not preserved"
        
        # Verify DICM prefix
        assert received_bytes[128:132] == b'DICM', \
            "DICM prefix not preserved"
    
    def test_forward_file_size_matches(self, sample_dicom_file, mock_scp_server):  # noqa: ARG002
        """Test that forwarded file size matches original."""
        original_bytes = read_dicom_bytes_sync(sample_dicom_file)
        original_size = len(original_bytes)
        
        # Forward file
        scu = CStoreSCU()
        success, _error, _stats = scu.forward_file(
            file_path=sample_dicom_file,
            remote_ae_title="TEST_SCP",
            remote_host="127.0.0.1",
            remote_port=mock_scp_server["port"],
        )
        
        time.sleep(0.5)
        
        assert success is True
        
        # Check received file size
        received_files = mock_scp_server["received_files"]
        assert len(received_files) > 0
        
        received_bytes = read_dicom_bytes_sync(received_files[0])
        received_size = len(received_bytes)
        
        assert received_size == original_size, \
            f"File size mismatch: original={original_size}, received={received_size}"
    
    def test_forward_multiple_files(self, tmp_path, mock_scp_server):  # noqa: ARG002
        """Test forwarding multiple files."""
        # Create multiple test files
        original_bytes = b'\x00' * 128 + b'DICM' + b'test_data'
        test_files = []
        
        for i in range(3):
            test_file = tmp_path / f"test_{i}.dcm"
            test_file.write_bytes(original_bytes)
            test_files.append(test_file)
        
        scu = CStoreSCU()
        
        # Forward all files
        for test_file in test_files:
            success, error, _stats = scu.forward_file(
                file_path=test_file,
                remote_ae_title="TEST_SCP",
                remote_host="127.0.0.1",
                remote_port=mock_scp_server["port"],
            )
            assert success is True, f"Failed to forward {test_file}: {error}"
            time.sleep(0.1)
        
        # Wait for all files to be received
        time.sleep(1.0)
        
        # Verify all files received
        received_files = mock_scp_server["received_files"]
        assert len(received_files) >= len(test_files), \
            f"Expected at least {len(test_files)} files, got {len(received_files)}"

