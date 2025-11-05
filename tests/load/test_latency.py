"""Load tests for latency measurement."""

import pytest
import asyncio
import time
import statistics
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.scp import CStoreSCP
from dicom_gw.dicom.scu import CStoreSCU


@pytest.fixture
def sample_dicom_file(tmp_path):
    """Create a sample DICOM file for latency testing."""
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
    
    dicom_file = tmp_path / "test.dcm"
    ds.save_as(dicom_file, write_like_original=True)
    
    return dicom_file


@pytest.mark.load
class TestLatency:
    """Load tests for latency measurement."""
    
    @pytest.mark.asyncio
    async def test_receive_latency(self, tmp_path, sample_dicom_file):
        """Test C-STORE receive latency (time per file)."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        scp = CStoreSCP(
            ae_title="LATENCY_TEST_SCP",
            port=0,
            storage_path=storage_dir,
        )
        
        scp.start()
        
        try:
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            latencies = []
            
            # Send file multiple times and measure latency
            for _ in range(50):
                start_time = time.time()
                
                assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="LATENCY_TEST_SCU")
                if assoc.is_established:
                    status = assoc.send_c_store(sample_dicom_file)
                    assoc.release()
                    
                    end_time = time.time()
                    latency = (end_time - start_time) * 1000  # Convert to ms
                    
                    if status.Status == 0x0000:
                        latencies.append(latency)
                
                await asyncio.sleep(0.01)
            
            if latencies:
                mean_latency = statistics.mean(latencies)
                median_latency = statistics.median(latencies)
                p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
                p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
                
                print("\nReceive Latency Test Results:")  # noqa: T201
                print(f"  Samples: {len(latencies)}")  # noqa: T201
                print(f"  Mean: {mean_latency:.2f}ms")  # noqa: T201
                print(f"  Median: {median_latency:.2f}ms")  # noqa: T201
                print(f"  P95: {p95_latency:.2f}ms")  # noqa: T201
                print(f"  P99: {p99_latency:.2f}ms")  # noqa: T201
                
                # Assert reasonable latency (adjust based on requirements)
                assert mean_latency < 1000, f"Mean latency too high: {mean_latency:.2f}ms"
                assert p95_latency < 2000, f"P95 latency too high: {p95_latency:.2f}ms"
        
        finally:
            scp.stop()
    
    def test_forward_latency(self, sample_dicom_file):  # noqa: ARG002
        """Test C-STORE forward latency (time per file)."""
        from pynetdicom import evt
        
        def handle_store(_event):
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
            scu = CStoreSCU()
            latencies = []
            
            # Forward file multiple times and measure latency
            for _ in range(50):
                start_time = time.time()
                
                success, _error, _stats = scu.forward_file(
                    file_path=sample_dicom_file,
                    remote_ae_title="MOCK_SCP",
                    remote_host="127.0.0.1",
                    remote_port=mock_port,
                )
                
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convert to ms
                
                if success:
                    latencies.append(latency)
            
            if latencies:
                mean_latency = statistics.mean(latencies)
                median_latency = statistics.median(latencies)
                p95_latency = statistics.quantiles(latencies, n=20)[18]
                p99_latency = statistics.quantiles(latencies, n=100)[98]
                
                print("\nForward Latency Test Results:")  # noqa: T201
                print(f"  Samples: {len(latencies)}")  # noqa: T201
                print(f"  Mean: {mean_latency:.2f}ms")  # noqa: T201
                print(f"  Median: {median_latency:.2f}ms")  # noqa: T201
                print(f"  P95: {p95_latency:.2f}ms")  # noqa: T201
                print(f"  P99: {p99_latency:.2f}ms")  # noqa: T201
                
                # Assert reasonable latency
                assert mean_latency < 2000, f"Mean latency too high: {mean_latency:.2f}ms"
                assert p95_latency < 5000, f"P95 latency too high: {p95_latency:.2f}ms"
        
        finally:
            if mock_server:
                mock_server.shutdown()
    
    @pytest.mark.asyncio
    async def test_file_io_latency(self, tmp_path, sample_dicom_file):
        """Test file I/O latency (read/write operations)."""
        from dicom_gw.dicom.io import write_dicom_bytes_sync
        
        read_latencies = []
        write_latencies = []
        
        # Test read latency
        for _ in range(100):
            start_time = time.time()
            _bytes = read_dicom_bytes_sync(sample_dicom_file)
            end_time = time.time()
            read_latencies.append((end_time - start_time) * 1000)
        
        # Test write latency
        test_file = tmp_path / "test_write.dcm"
        original_bytes = read_dicom_bytes_sync(sample_dicom_file)
        
        for _ in range(100):
            start_time = time.time()
            write_dicom_bytes_sync(test_file, original_bytes)
            end_time = time.time()
            write_latencies.append((end_time - start_time) * 1000)
        
        # Clean up
        test_file.unlink()
        
        read_mean = statistics.mean(read_latencies)
        write_mean = statistics.mean(write_latencies)
        
        print("\nFile I/O Latency Test Results:")  # noqa: T201
        print(f"  Read Mean: {read_mean:.2f}ms")  # noqa: T201
        print(f"  Write Mean: {write_mean:.2f}ms")  # noqa: T201
        
        # Assert reasonable I/O latency
        assert read_mean < 10, f"Read latency too high: {read_mean:.2f}ms"
        assert write_mean < 50, f"Write latency too high: {write_mean:.2f}ms"

