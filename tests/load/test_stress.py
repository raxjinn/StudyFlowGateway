"""Stress tests for system under extreme load."""

import pytest
import asyncio
import time
import os
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage  # type: ignore[attr-defined]
from dicom_gw.dicom.scp import CStoreSCP


@pytest.fixture
def large_dicom_files(tmp_path, count=20):
    """Create larger DICOM files for stress testing."""
    files = []
    for i in range(count):
        ds = FileDataset(f"large_{i}.dcm", {}, file_meta=Dataset(), preamble=b"\x00" * 128)
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
        ds.file_meta.MediaStorageSOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
        
        ds.SOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
        ds.StudyInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}S"
        ds.SeriesInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}SE"
        ds.PatientID = f"STRESS{i:04d}"
        ds.Modality = "CT"
        
        # Add some dummy pixel data to make file larger
        # This is a simplified approach - real pixel data would be more complex
        ds.PixelData = b'\x00' * (1024 * 1024)  # 1MB of dummy data
        
        dicom_file = tmp_path / f"large_{i}.dcm"
        ds.save_as(dicom_file, write_like_original=True)
        files.append(dicom_file)
    
    return files


@pytest.mark.load
@pytest.mark.slow
class TestStress:
    """Stress tests for system under extreme load."""
    
    @pytest.mark.asyncio
    async def test_sustained_load(self, tmp_path):
        """Test system under sustained load for extended period."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        # Create test files
        test_files = []
        for i in range(100):
            ds = FileDataset(f"test_{i}.dcm", {}, file_meta=Dataset(), preamble=b"\x00" * 128)
            ds.is_little_endian = True
            ds.is_implicit_VR = False
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
            ds.file_meta.MediaStorageSOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
            
            ds.SOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
            ds.StudyInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}S"
            ds.PatientID = f"STRESS{i:04d}"
            ds.Modality = "CT"
            
            dicom_file = tmp_path / f"test_{i}.dcm"
            ds.save_as(dicom_file, write_like_original=True)
            test_files.append(dicom_file)
        
        scp = CStoreSCP(
            ae_title="STRESS_TEST_SCP",
            port=0,
            storage_path=storage_dir,
        )
        
        scp.start()
        
        try:
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            successful = 0
            failed = 0
            start_time = time.time()
            
            # Run for sustained period (30 seconds)
            while time.time() - start_time < 30:
                for dicom_file in test_files:
                    if time.time() - start_time >= 30:
                        break
                    
                    try:
                        assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="STRESS_TEST_SCU")
                        if assoc.is_established:
                            status = assoc.send_c_store(dicom_file)
                            if status.Status == 0x0000:
                                successful += 1
                            else:
                                failed += 1
                            assoc.release()
                        else:
                            failed += 1
                    except Exception:  # noqa: BLE001
                        failed += 1
                    
                    await asyncio.sleep(0.05)
            
            duration = time.time() - start_time
            throughput = successful / duration if duration > 0 else 0
            
            print("\nSustained Load Test Results:")  # noqa: T201
            print(f"  Duration: {duration:.2f}s")  # noqa: T201
            print(f"  Successful: {successful}")  # noqa: T201
            print(f"  Failed: {failed}")  # noqa: T201
            print(f"  Throughput: {throughput:.2f} files/second")  # noqa: T201
            
            # System should remain stable
            assert failed / (successful + failed) < 0.1, \
                f"Failure rate too high: {failed / (successful + failed) * 100:.1f}%"
        
        finally:
            scp.stop()
    
    @pytest.mark.asyncio
    async def test_burst_load(self, tmp_path, large_dicom_files):
        """Test system under burst load (many files at once)."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        scp = CStoreSCP(
            ae_title="BURST_TEST_SCP",
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
                    assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="BURST_TEST_SCU")
                    if assoc.is_established:
                        status = assoc.send_c_store(dicom_file)
                        assoc.release()
                        return status.Status == 0x0000
                    return False
                except Exception:  # noqa: BLE001
                    return False
            
            # Send all files at once (burst)
            start_time = time.time()
            results = await asyncio.gather(*[send_file(f) for f in large_dicom_files])
            end_time = time.time()
            
            successful = sum(results)
            duration = end_time - start_time
            
            print("\nBurst Load Test Results:")  # noqa: T201
            print(f"  Files sent: {len(large_dicom_files)}")  # noqa: T201
            print(f"  Successful: {successful}")  # noqa: T201
            print(f"  Duration: {duration:.2f}s")  # noqa: T201
            print(f"  Rate: {successful / duration:.2f} files/second")  # noqa: T201
            
            # System should handle burst load
            assert successful > len(large_dicom_files) * 0.8, \
                f"Burst load handling poor: {successful}/{len(large_dicom_files)}"
        
        finally:
            scp.stop()
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, tmp_path):
        """Test memory usage under load."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not available")
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        
        scp = CStoreSCP(
            ae_title="MEMORY_TEST_SCP",
            port=0,
            storage_path=storage_dir,
        )
        
        scp.start()
        
        try:
            # Create and send many files
            test_files = []
            for i in range(200):
                ds = FileDataset(f"test_{i}.dcm", {}, file_meta=Dataset(), preamble=b"\x00" * 128)
                ds.is_little_endian = True
                ds.is_implicit_VR = False
                ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
                ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
                ds.file_meta.MediaStorageSOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
                
                ds.SOPInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}"
                ds.StudyInstanceUID = f"1.2.3.4.5.6.7.8.9.{i:04d}S"
                ds.PatientID = f"MEM{i:04d}"
                ds.Modality = "CT"
                
                dicom_file = tmp_path / f"test_{i}.dcm"
                ds.save_as(dicom_file, write_like_original=True)
                test_files.append(dicom_file)
            
            # Send files
            ae_client = AE()
            ae_client.add_requested_context(CTImageStorage)
            
            for dicom_file in test_files:
                assoc = ae_client.associate("127.0.0.1", scp.port, ae_title="MEMORY_TEST_SCU")
                if assoc.is_established:
                    assoc.send_c_store(dicom_file)
                    assoc.release()
                await asyncio.sleep(0.01)
            
            # Wait for processing
            await asyncio.sleep(2.0)
            
            # Check memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            print("\nMemory Usage Test Results:")  # noqa: T201
            print(f"  Initial memory: {initial_memory:.2f} MB")  # noqa: T201
            print(f"  Final memory: {final_memory:.2f} MB")  # noqa: T201
            print(f"  Increase: {memory_increase:.2f} MB")  # noqa: T201
            
            # Memory increase should be reasonable (< 500MB for 200 files)
            assert memory_increase < 500, \
                f"Memory increase too high: {memory_increase:.2f} MB"
        
        finally:
            scp.stop()

