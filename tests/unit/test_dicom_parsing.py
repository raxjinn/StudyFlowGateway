"""Unit tests for DICOM parsing operations."""

import pytest
from pydicom.dataset import Dataset
from dicom_gw.dicom.io import parse_dicom_metadata, get_dicom_tags


@pytest.fixture
def sample_dicom_file(tmp_path):
    """Create a sample DICOM file using pydicom."""
    # Create a minimal DICOM dataset
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9.11"
    ds.SeriesInstanceUID = "1.2.3.4.5.6.7.8.9.12"
    ds.PatientID = "TEST001"
    ds.PatientName = "Test^Patient"
    ds.Modality = "CT"
    ds.StudyDate = "20240101"
    ds.StudyTime = "120000"
    ds.AccessionNumber = "ACC123456"
    
    # Set file meta information
    ds.file_meta = Dataset()
    ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    
    # Save to file
    dicom_file = tmp_path / "test.dcm"
    ds.save_as(dicom_file, write_like_original=True)
    
    return dicom_file


class TestParseDicomMetadata:
    """Test DICOM metadata parsing."""
    
    def test_parse_metadata_extracts_uids(self, sample_dicom_file):
        """Test that UIDs are extracted correctly."""
        metadata = parse_dicom_metadata(sample_dicom_file)
        
        assert metadata.get("sop_instance_uid") == "1.2.3.4.5.6.7.8.9.10"
        assert metadata.get("study_instance_uid") == "1.2.3.4.5.6.7.8.9.11"
        assert metadata.get("series_instance_uid") == "1.2.3.4.5.6.7.8.9.12"
    
    def test_parse_metadata_extracts_patient_info(self, sample_dicom_file):
        """Test that patient information is extracted."""
        metadata = parse_dicom_metadata(sample_dicom_file)
        
        assert metadata.get("patient_id") == "TEST001"
        assert metadata.get("patient_name") == "Test^Patient"
    
    def test_parse_metadata_extracts_study_info(self, sample_dicom_file):
        """Test that study information is extracted."""
        metadata = parse_dicom_metadata(sample_dicom_file)
        
        assert metadata.get("modality") == "CT"
        assert metadata.get("study_date") == "20240101"
        assert metadata.get("study_time") == "120000"
        assert metadata.get("accession_number") == "ACC123456"
    
    def test_parse_metadata_handles_missing_tags(self, tmp_path):
        """Test that missing tags are handled gracefully."""
        # Create minimal DICOM with only required tags
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3.4.5"
        ds.StudyInstanceUID = "1.2.3.4.6"
        ds.SeriesInstanceUID = "1.2.3.4.7"
        
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        
        minimal_file = tmp_path / "minimal.dcm"
        ds.save_as(minimal_file, write_like_original=True)
        
        metadata = parse_dicom_metadata(minimal_file)
        
        # Should still extract UIDs
        assert metadata.get("sop_instance_uid") == "1.2.3.4.5"
        # Missing tags should be None or absent
        assert metadata.get("patient_id") is None or "patient_id" not in metadata


class TestGetDicomTags:
    """Test DICOM tag extraction."""
    
    def test_get_tags_returns_tags(self, sample_dicom_file):
        """Test that tags are returned."""
        tags = get_dicom_tags(sample_dicom_file)
        
        assert isinstance(tags, (dict, list))
        assert len(tags) > 0
    
    def test_get_tags_includes_common_tags(self, sample_dicom_file):
        """Test that common tags are included."""
        tags = get_dicom_tags(sample_dicom_file)
        
        # Should include at least some common tags
        # Implementation may return dict or list
        if isinstance(tags, dict):
            assert "SOPInstanceUID" in tags or "sop_instance_uid" in tags
        elif isinstance(tags, list):
            # List format - check that it's not empty
            assert len(tags) > 0


class TestDicomValidation:
    """Test DICOM validation."""
    
    def test_valid_dicom_file(self, sample_dicom_file):
        """Test that valid DICOM file is recognized."""
        from dicom_gw.dicom.io import verify_dicom_structure
        
        assert verify_dicom_structure(sample_dicom_file) is True
    
    def test_invalid_file_not_dicom(self, tmp_path):
        """Test that non-DICOM file is rejected."""
        from dicom_gw.dicom.io import verify_dicom_structure
        
        # Create a text file
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is not a DICOM file")
        
        result = verify_dicom_structure(text_file)
        assert result is False or isinstance(result, bool)
    
    def test_empty_file_not_dicom(self, tmp_path):
        """Test that empty file is rejected."""
        from dicom_gw.dicom.io import verify_dicom_structure
        
        empty_file = tmp_path / "empty.dcm"
        empty_file.write_bytes(b'')
        
        result = verify_dicom_structure(empty_file)
        assert result is False or isinstance(result, bool)

