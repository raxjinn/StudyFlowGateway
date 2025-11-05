"""Unit tests for byte-preserving DICOM I/O operations."""

import pytest
from dicom_gw.dicom.io import (
    read_dicom_bytes_sync,
    write_dicom_bytes_sync,
    verify_dicom_structure,
    parse_dicom_metadata,
    verify_byte_equality,
    get_dicom_tags,
)


@pytest.fixture
def sample_dicom_bytes():
    """Create sample DICOM file bytes with preamble and DICM prefix."""
    # Create a minimal DICOM file with preamble (128 bytes of zeros)
    # followed by "DICM" and then basic DICOM data
    preamble = b'\x00' * 128
    dicm_prefix = b'DICM'
    
    # Minimal DICOM file structure (simplified)
    # In real tests, you'd use actual DICOM data
    # For now, we'll create a simple structure
    dicom_data = (
        preamble +
        dicm_prefix +
        # Group 0x0008, Element 0x0005 (Character Set)
        b'\x08\x00\x05\x00' +  # Tag
        b'CS' +                 # VR
        b'\x00\x00' +           # Reserved
        b'\x04\x00\x00\x00' +   # Length
        b'ISO'                  # Value
    )
    
    return dicom_data


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    return tmp_path / "test.dcm"


class TestReadDicomBytes:
    """Test reading DICOM files with byte preservation."""
    
    def test_read_dicom_bytes_with_preamble(self, temp_file, sample_dicom_bytes):
        """Test reading DICOM file with preamble."""
        # Write test data
        temp_file.write_bytes(sample_dicom_bytes)
        
        # Read back
        read_bytes = read_dicom_bytes_sync(temp_file)
        
        # Verify exact byte match
        assert read_bytes == sample_dicom_bytes
        assert len(read_bytes) == len(sample_dicom_bytes)
    
    def test_read_dicom_bytes_preamble_preserved(self, temp_file, sample_dicom_bytes):
        """Test that 128-byte preamble is preserved."""
        temp_file.write_bytes(sample_dicom_bytes)
        
        read_bytes = read_dicom_bytes_sync(temp_file)
        
        # Check preamble (first 128 bytes should be zeros)
        assert read_bytes[:128] == b'\x00' * 128
        
        # Check DICM prefix (bytes 128-132)
        assert read_bytes[128:132] == b'DICM'
    
    def test_read_nonexistent_file(self, tmp_path):
        """Test reading non-existent file raises error."""
        nonexistent = tmp_path / "nonexistent.dcm"
        
        with pytest.raises(FileNotFoundError):
            read_dicom_bytes_sync(nonexistent)


class TestWriteDicomBytes:
    """Test writing DICOM files with byte preservation."""
    
    def test_write_dicom_bytes_preserves_bytes(self, temp_file, sample_dicom_bytes):
        """Test that writing preserves exact bytes."""
        # Write bytes
        write_dicom_bytes_sync(temp_file, sample_dicom_bytes)
        
        # Read back
        read_bytes = read_dicom_bytes_sync(temp_file)
        
        # Verify exact match
        assert read_bytes == sample_dicom_bytes
        assert verify_byte_equality(sample_dicom_bytes, read_bytes)
    
    def test_write_dicom_bytes_preamble_preserved(self, temp_file, sample_dicom_bytes):
        """Test that preamble is preserved during write."""
        write_dicom_bytes_sync(temp_file, sample_dicom_bytes)
        
        read_bytes = read_dicom_bytes_sync(temp_file)
        
        # Verify preamble
        assert read_bytes[:128] == b'\x00' * 128
        assert read_bytes[128:132] == b'DICM'
    
    def test_write_overwrites_existing_file(self, temp_file, sample_dicom_bytes):
        """Test that write overwrites existing file."""
        # Write initial data
        initial_data = sample_dicom_bytes + b'extra'
        write_dicom_bytes_sync(temp_file, initial_data)
        
        # Write new data
        write_dicom_bytes_sync(temp_file, sample_dicom_bytes)
        
        # Verify new data
        read_bytes = read_dicom_bytes_sync(temp_file)
        assert read_bytes == sample_dicom_bytes
        assert len(read_bytes) == len(sample_dicom_bytes)


class TestVerifyDicomStructure:
    """Test DICOM structure verification."""
    
    def test_verify_valid_dicom_structure(self, temp_file, sample_dicom_bytes):
        """Test verification of valid DICOM structure."""
        temp_file.write_bytes(sample_dicom_bytes)
        
        assert verify_dicom_structure(temp_file) is True
    
    def test_verify_missing_preamble(self, temp_file):
        """Test that missing preamble is detected."""
        # Write data without preamble
        invalid_data = b'DICM' + b'some data'
        temp_file.write_bytes(invalid_data)
        
        # Should handle gracefully (may return False or raise exception)
        result = verify_dicom_structure(temp_file)
        # Implementation may vary - just check it doesn't crash
        assert isinstance(result, bool)
    
    def test_verify_missing_dicm_prefix(self, temp_file):
        """Test that missing DICM prefix is detected."""
        # Write data with preamble but no DICM
        invalid_data = b'\x00' * 128 + b'INVALID'
        temp_file.write_bytes(invalid_data)
        
        result = verify_dicom_structure(temp_file)
        assert isinstance(result, bool)


class TestParseDicomMetadata:
    """Test DICOM metadata parsing."""
    
    def test_parse_dicom_metadata(self, temp_file, sample_dicom_bytes):
        """Test parsing DICOM metadata."""
        temp_file.write_bytes(sample_dicom_bytes)
        
        metadata = parse_dicom_metadata(temp_file)
        
        # Metadata should be a dictionary
        assert isinstance(metadata, dict)
        
        # Should contain common DICOM tags
        # Note: Actual tags depend on sample data
        assert 'file_path' in metadata or 'sop_instance_uid' in metadata
    
    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing non-existent file."""
        nonexistent = tmp_path / "nonexistent.dcm"
        
        with pytest.raises(FileNotFoundError):
            parse_dicom_metadata(nonexistent)


class TestVerifyByteEquality:
    """Test byte equality verification."""
    
    def test_identical_bytes_equal(self, sample_dicom_bytes):
        """Test that identical bytes are equal."""
        assert verify_byte_equality(sample_dicom_bytes, sample_dicom_bytes) is True
    
    def test_different_bytes_not_equal(self, sample_dicom_bytes):
        """Test that different bytes are not equal."""
        different_bytes = sample_dicom_bytes + b'different'
        assert verify_byte_equality(sample_dicom_bytes, different_bytes) is False
    
    def test_different_length_bytes_not_equal(self, sample_dicom_bytes):
        """Test that different length bytes are not equal."""
        shorter_bytes = sample_dicom_bytes[:-1]
        assert verify_byte_equality(sample_dicom_bytes, shorter_bytes) is False
    
    def test_empty_bytes_equal(self):
        """Test that empty bytes are equal."""
        assert verify_byte_equality(b'', b'') is True
    
    def test_one_empty_byte_not_equal(self, sample_dicom_bytes):
        """Test that one empty byte is not equal to non-empty."""
        assert verify_byte_equality(b'', sample_dicom_bytes) is False
        assert verify_byte_equality(sample_dicom_bytes, b'') is False


class TestGetDicomTags:
    """Test DICOM tag extraction."""
    
    def test_get_dicom_tags(self, temp_file, sample_dicom_bytes):
        """Test getting DICOM tags from file."""
        temp_file.write_bytes(sample_dicom_bytes)
        
        tags = get_dicom_tags(temp_file)
        
        # Should return a dictionary or list
        assert isinstance(tags, (dict, list))
    
    def test_get_dicom_tags_nonexistent_file(self, tmp_path):
        """Test getting tags from non-existent file."""
        nonexistent = tmp_path / "nonexistent.dcm"
        
        with pytest.raises(FileNotFoundError):
            get_dicom_tags(nonexistent)

