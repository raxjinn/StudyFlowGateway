"""End-to-end integration tests for receive -> forward workflow."""

import pytest
import asyncio
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE, evt
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.io import read_dicom_bytes_sync, verify_byte_equality
from dicom_gw.dicom.scp import CStoreSCP
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
def mock_destination_scp(tmp_path):
    """Create a mock destination SCP server."""
    received_files = []
    
    def handle_store(event):
        """Handle C-STORE request."""
        received_file = tmp_path / f"received_{len(received_files)}.dcm"
        event.dataset.save_as(received_file, write_like_original=True)
        received_files.append(received_file)
        return 0x0000
    
    handlers = [(evt.EVT_C_STORE, handle_store)]
    
    ae = AE()
    ae.add_supported_context(CTImageStorage)
    
    server = ae.start_server(("127.0.0.1", 0), evt_handlers=handlers, block=False)
    port = server.socket.getsockname()[1]
    
    yield {
        "server": server,
        "port": port,
        "received_files": received_files,
    }
    
    server.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndWorkflow:
    """Test complete receive -> forward workflow with byte preservation."""
    
    async def test_receive_and_forward_preserves_bytes(
        self, tmp_path, sample_dicom_file, mock_destination_scp  # noqa: ARG002
    ):
        """Test that bytes are preserved through receive -> forward workflow."""
        # Get original bytes
        original_bytes = read_dicom_bytes_sync(sample_dicom_file)
        
        # Setup storage directory
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        # Create SCP receiver
        scp = CStoreSCP(
            ae_title="GATEWAY_SCP",
            port=0,
            storage_path=str(storage_dir),
        )
        
        scp.start()
        
        try:
            # Step 1: Receive file via C-STORE
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            assoc = ae_client.associate("127.0.0.1", scp.port)
            if assoc.is_established:
                status = assoc.send_c_store(sample_dicom_file)
                assert status.Status == 0x0000
                assoc.release()
            
            # Wait for file to be stored
            await asyncio.sleep(0.5)
            
            # Find received file
            received_files = list(storage_dir.rglob("*.dcm"))
            assert len(received_files) > 0, "File not received"
            
            stored_file = received_files[0]
            stored_bytes = read_dicom_bytes_sync(stored_file)
            
            # Verify received file matches original
            assert verify_byte_equality(original_bytes, stored_bytes), \
                "Received file does not match original"
            
            # Step 2: Forward file via C-STORE SCU
            scu = CStoreSCU()
            success, error, _stats = scu.forward_file(
                file_path=stored_file,
                remote_ae_title="DEST_SCP",
                remote_host="127.0.0.1",
                remote_port=mock_destination_scp["port"],
            )
            
            assert success is True, f"Forward failed: {error}"
            
            # Wait for destination to receive
            await asyncio.sleep(0.5)
            
            # Verify destination received file
            dest_received = mock_destination_scp["received_files"]
            assert len(dest_received) > 0, "File not received at destination"
            
            forwarded_bytes = read_dicom_bytes_sync(dest_received[0])
            
            # Verify forwarded file matches original (byte-for-byte)
            assert verify_byte_equality(original_bytes, forwarded_bytes), \
                "Forwarded file does not match original"
            
            # Verify all three files are identical
            assert verify_byte_equality(stored_bytes, forwarded_bytes), \
                "Stored and forwarded files do not match"
            
            # Verify preamble and DICM prefix at each stage
            for name, bytes_data in [
                ("original", original_bytes),
                ("stored", stored_bytes),
                ("forwarded", forwarded_bytes),
            ]:
                assert bytes_data[:128] == b'\x00' * 128, \
                    f"{name} file: preamble not preserved"
                assert bytes_data[128:132] == b'DICM', \
                    f"{name} file: DICM prefix not preserved"
        
        finally:
            scp.stop()
    
    async def test_multiple_files_end_to_end(self, tmp_path, mock_destination_scp):  # noqa: ARG002
        """Test receiving and forwarding multiple files."""
        # Create multiple test files
        original_data = b'\x00' * 128 + b'DICM' + b'test_data_'
        test_files = []
        
        for i in range(3):
            test_file = tmp_path / f"test_{i}.dcm"
            file_data = original_data + str(i).encode()
            test_file.write_bytes(file_data)
            test_files.append(test_file)
        
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        scp = CStoreSCP(
            ae_title="GATEWAY_SCP",
            port=0,
            storage_path=str(storage_dir),
        )
        
        scp.start()
        
        try:
            # Receive all files
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            for test_file in test_files:
                assoc = ae_client.associate("127.0.0.1", scp.port)
                if assoc.is_established:
                    status = assoc.send_c_store(test_file)
                    assert status.Status == 0x0000
                    assoc.release()
                await asyncio.sleep(0.1)
            
            await asyncio.sleep(1.0)
            
            # Find all received files
            stored_files = list(storage_dir.rglob("*.dcm"))
            assert len(stored_files) >= len(test_files)
            
            # Forward all stored files
            scu = CStoreSCU()
            for stored_file in stored_files[:len(test_files)]:  # Forward first N files
                success, error, _stats = scu.forward_file(
                    file_path=stored_file,
                    remote_ae_title="DEST_SCP",
                    remote_host="127.0.0.1",
                    remote_port=mock_destination_scp["port"],
                )
                assert success is True, f"Failed to forward {stored_file}: {error}"
                await asyncio.sleep(0.1)
            
            await asyncio.sleep(1.0)
            
            # Verify all files forwarded
            dest_received = mock_destination_scp["received_files"]
            assert len(dest_received) >= len(test_files), \
                f"Expected at least {len(test_files)} files at destination"
        
        finally:
            scp.stop()

