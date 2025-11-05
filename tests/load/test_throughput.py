"""Load tests for throughput measurement."""

import pytest
import asyncio
import time
from pathlib import Path
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.scp import CStoreSCP
from dicom_gw.dicom.scu import CStoreSCU


@pytest.fixture
def sample_dicom_files(tmp_path, count=100):
    """Create multiple sample DICOM files for load testing."""
    files = []
    for i in range(count):
        ds = FileDataset(f"test_{i}.dcm", {}, file_meta=Dataset(), preamble=b"\x00" * 128)
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
        ds.file_meta.MediaStorageSOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
        
        ds.SOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
        ds.StudyInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}S"
        ds.SeriesInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}SE"
        ds.PatientID = f"TEST{i:04d}"
        ds.PatientName = f"Test^Patient{i:04d}"
        ds.Modality = "CT"
        ds.StudyDate = "20240101"
        
        dicom_file = tmp_path / f"test_{i}.dcm"
        ds.save_as(dicom_file, write_like_original=True)
        files.append(dicom_file)
    
    return files


@pytest.mark.load
@pytest.mark.slow
class TestThroughput:
    """Load tests for throughput measurement."""
    
    @pytest.mark.asyncio
    async def test_receive_throughput(self, tmp_path, sample_dicom_files):
        """Test C-STORE receive throughput (files per second)."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        # Create SCP
        scp = CStoreSCP(
            ae_title="LOAD_TEST_SCP",
            port=0,
            storage_path=str(storage_dir),
        )
        
        scp.start()
        
        try:
            # Create SCU client
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            # Send files and measure time
            start_time = time.time()
            successful = 0
            failed = 0
            
            for dicom_file in sample_dicom_files:
                try:
                    assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="LOAD_TEST_SCU")
                    if assoc.is_established:
                        status = assoc.send_c_store(dicom_file)
                        if status.Status == 0x0000:
                            successful += 1
                        else:
                            failed += 1
                        assoc.release()
                    else:
                        failed += 1
                except Exception as e:  # noqa: BLE001
                    print(f"Error sending {dicom_file}: {e}")  # noqa: T201
                    failed += 1
                
                # Small delay to avoid overwhelming
                await asyncio.sleep(0.01)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate throughput
            throughput = successful / duration if duration > 0 else 0
            
            print("\nReceive Throughput Test Results:")  # noqa: T201
            print(f"  Files sent: {len(sample_dicom_files)}")  # noqa: T201
            print(f"  Successful: {successful}")  # noqa: T201
            print(f"  Failed: {failed}")  # noqa: T201
            print(f"  Duration: {duration:.2f}s")  # noqa: T201
            print(f"  Throughput: {throughput:.2f} files/second")  # noqa: T201
            
            # Assert minimum throughput (adjust based on requirements)
            assert throughput > 10, f"Throughput too low: {throughput:.2f} files/s"
            assert successful > len(sample_dicom_files) * 0.95, \
                f"Success rate too low: {successful}/{len(sample_dicom_files)}"
        
        finally:
            scp.stop()
    
    def test_forward_throughput(self, sample_dicom_files):  # noqa: ARG002
        """Test C-STORE forward throughput (files per second)."""
        # Create mock SCP server
        from pynetdicom import evt
        
        received_count = {"count": 0}
        
        def handle_store(_event):
            received_count["count"] += 1
            return 0x0000
        
        handlers = [(evt.EVT_C_STORE, handle_store)]
        
        mock_ae = AE()
        mock_ae.add_supported_context(CTImageStorage)
        mock_server = mock_ae.start_server(
            ("127.0.0.1", 0),
            evt_handlers=handlers,  # type: ignore[arg-type]
            block=False
        )
        if mock_server and mock_server.socket:
            mock_port = mock_server.socket.getsockname()[1]
        else:
            pytest.skip("Failed to start mock server")
        
        try:
            # Forward files and measure time
            scu = CStoreSCU()
            
            start_time = time.time()
            successful = 0
            failed = 0
            
            for dicom_file in sample_dicom_files:
                success, error, _stats = scu.forward_file(
                    file_path=dicom_file,
                    remote_ae_title="MOCK_SCP",
                    remote_host="127.0.0.1",
                    remote_port=mock_port,
                )
                
                if success:
                    successful += 1
                else:
                    failed += 1
                    print(f"Forward failed: {error}")
            
            # Wait for all files to be received
            time.sleep(2.0)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate throughput
            throughput = successful / duration if duration > 0 else 0
            
            print("\nForward Throughput Test Results:")  # noqa: T201
            print(f"  Files sent: {len(sample_dicom_files)}")  # noqa: T201
            print(f"  Successful: {successful}")  # noqa: T201
            print(f"  Failed: {failed}")  # noqa: T201
            print(f"  Received: {received_count['count']}")  # noqa: T201
            print(f"  Duration: {duration:.2f}s")  # noqa: T201
            print(f"  Throughput: {throughput:.2f} files/second")  # noqa: T201
            
            # Assert minimum throughput
            assert throughput > 5, f"Throughput too low: {throughput:.2f} files/s"
            assert successful > len(sample_dicom_files) * 0.90, \
                f"Success rate too low: {successful}/{len(sample_dicom_files)}"
        
        finally:
            if mock_server:
                mock_server.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_receive_throughput(self, tmp_path, sample_dicom_files):
        """Test concurrent C-STORE receive throughput."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        scp = CStoreSCP(
            ae_title="LOAD_TEST_SCP",
            port=0,
            storage_path=storage_dir,
        )
        
        scp.start()
        
        try:
            async def send_file(dicom_file):
                """Send a single file."""
                ae_client = AE()
                ae_client.add_requested_context(CTImageStorage)
                
                try:
                    assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="LOAD_TEST_SCU")
                    if assoc.is_established:
                        status = assoc.send_c_store(dicom_file)
                        assoc.release()
                        return status.Status == 0x0000
                    return False
                except Exception:  # noqa: BLE001
                    return False
            
            # Send files concurrently
            start_time = time.time()
            results = await asyncio.gather(*[send_file(f) for f in sample_dicom_files[:50]])
            end_time = time.time()
            
            successful = sum(results)
            duration = end_time - start_time
            throughput = successful / duration if duration > 0 else 0
            
            print("\nConcurrent Receive Throughput Test Results:")  # noqa: T201
            print(f"  Files sent: {len(results)}")  # noqa: T201
            print(f"  Successful: {successful}")  # noqa: T201
            print(f"  Duration: {duration:.2f}s")  # noqa: T201
            print(f"  Throughput: {throughput:.2f} files/second")  # noqa: T201
            
            assert throughput > 15, f"Concurrent throughput too low: {throughput:.2f} files/s"
        
        finally:
            scp.stop()

