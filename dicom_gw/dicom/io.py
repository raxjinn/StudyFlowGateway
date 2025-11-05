"""Byte-preserving DICOM I/O module.

This module ensures that DICOM files are read and written exactly as received,
preserving the 128-byte preamble and 4-byte "DICM" prefix without any modification.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
import aiofiles
import pydicom
from pydicom.dataset import Dataset
# InvalidDICOMError doesn't exist in newer pydicom versions
# Use generic Exception or ValueError instead
InvalidDICOMError = ValueError

logger = logging.getLogger(__name__)

# DICOM magic numbers
DICOM_PREAMBLE_SIZE = 128
DICOM_PREFIX = b"DICM"
DICOM_PREFIX_SIZE = 4


def verify_dicom_structure(file_path: Path) -> Tuple[bool, Optional[str], bool]:
    """Verify that a file has proper DICOM structure (preamble + DICM prefix).
    
    Args:
        file_path: Path to the DICOM file
    
    Returns:
        Tuple of (is_valid, error_message, has_preamble)
        - is_valid: True if file is valid DICOM
        - error_message: Error description if invalid, None if valid
        - has_preamble: True if file has 128-byte preamble
    """
    try:
        with open(file_path, "rb") as f:
            # Check file size (must be at least 132 bytes: 128 preamble + 4 prefix)
            file_size = f.seek(0, 2)
            if file_size < DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE:
                return (
                    False,
                    f"File too small ({file_size} bytes, minimum {DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE})",
                    False,
                )
            
            # Check for preamble and prefix
            f.seek(0)
            preamble = f.read(DICOM_PREAMBLE_SIZE)
            prefix = f.read(DICOM_PREFIX_SIZE)
            
            if prefix == DICOM_PREFIX:
                return (True, None, True)
            
            # Some DICOM files might not have preamble (non-standard but valid)
            # Check if file starts with DICM directly
            f.seek(0)
            if f.read(DICOM_PREFIX_SIZE) == DICOM_PREFIX:
                return (True, None, False)
            
            return (
                False,
                f"File does not contain DICM prefix (found: {prefix[:4]})",
                False,
            )
    except Exception as e:
        return (False, f"Error reading file: {str(e)}", False)


async def read_dicom_bytes(file_path: Path) -> bytes:
    """Read a DICOM file as raw bytes, preserving all data exactly.
    
    This function reads the entire file in binary mode without any parsing
    or modification, ensuring the 128-byte preamble and DICM prefix are preserved.
    
    Args:
        file_path: Path to the DICOM file
    
    Returns:
        Raw bytes of the DICOM file
    
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
    """
    async with aiofiles.open(file_path, "rb") as f:
        content = await f.read()
    
    # Verify structure
    is_valid, error_msg, has_preamble = verify_dicom_structure(file_path)
    if not is_valid:
        logger.warning(f"DICOM structure verification failed for {file_path}: {error_msg}")
        # Still return bytes even if structure is questionable
    
    return content


def read_dicom_bytes_sync(file_path: Path) -> bytes:
    """Synchronous version of read_dicom_bytes.
    
    Args:
        file_path: Path to the DICOM file
    
    Returns:
        Raw bytes of the DICOM file
    """
    with open(file_path, "rb") as f:
        content = f.read()
    
    # Verify structure
    is_valid, error_msg, has_preamble = verify_dicom_structure(file_path)
    if not is_valid:
        logger.warning(f"DICOM structure verification failed for {file_path}: {error_msg}")
    
    return content


async def write_dicom_bytes(file_path: Path, data: bytes, create_dirs: bool = True) -> int:
    """Write DICOM data as raw bytes, preserving all data exactly.
    
    This function writes the bytes directly to disk without any encoding
    or modification, ensuring the 128-byte preamble and DICM prefix are preserved.
    
    Args:
        file_path: Destination path for the DICOM file
        data: Raw bytes of the DICOM file
        create_dirs: If True, create parent directories if they don't exist
    
    Returns:
        Number of bytes written
    
    Raises:
        IOError: If file cannot be written
    """
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Verify structure before writing
    if len(data) < DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE:
        raise ValueError(
            f"Data too small ({len(data)} bytes, minimum {DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE})"
        )
    
    # Check for DICM prefix
    if len(data) >= DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE:
        prefix = data[DICOM_PREAMBLE_SIZE : DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE]
        if prefix != DICOM_PREFIX:
            # Check if data starts directly with DICM (no preamble)
            if data[:DICOM_PREFIX_SIZE] != DICOM_PREFIX:
                logger.warning(
                    f"Writing data without DICM prefix at expected location. "
                    f"Found: {prefix if len(prefix) == 4 else 'too short'}"
                )
    
    # Write bytes directly
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(data)
    
    # Set file permissions (readable by owner/group, not world)
    os.chmod(file_path, 0o640)
    
    return len(data)


def write_dicom_bytes_sync(file_path: Path, data: bytes, create_dirs: bool = True) -> int:
    """Synchronous version of write_dicom_bytes.
    
    Args:
        file_path: Destination path for the DICOM file
        data: Raw bytes of the DICOM file
        create_dirs: If True, create parent directories if they don't exist
    
    Returns:
        Number of bytes written
    """
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Verify structure before writing
    if len(data) < DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE:
        raise ValueError(
            f"Data too small ({len(data)} bytes, minimum {DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE})"
        )
    
    # Check for DICM prefix
    if len(data) >= DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE:
        prefix = data[DICOM_PREAMBLE_SIZE : DICOM_PREAMBLE_SIZE + DICOM_PREFIX_SIZE]
        if prefix != DICOM_PREFIX:
            if data[:DICOM_PREFIX_SIZE] != DICOM_PREFIX:
                logger.warning(
                    f"Writing data without DICM prefix at expected location. "
                    f"Found: {prefix if len(prefix) == 4 else 'too short'}"
                )
    
    # Write bytes directly
    with open(file_path, "wb") as f:
        written = f.write(data)
    
    # Set file permissions
    os.chmod(file_path, 0o640)
    
    return written


def parse_dicom_metadata(file_path: Path) -> Optional[Dataset]:
    """Parse DICOM file to extract metadata using pydicom.
    
    This function reads the file and parses it for metadata extraction only.
    The file itself is NOT modified. Use this for reading tags, not for writing.
    
    Args:
        file_path: Path to the DICOM file
    
    Returns:
        pydicom Dataset object, or None if parsing fails
    """
    try:
        # Use pydicom to parse metadata
        # Note: pydicom.read_file() should preserve the file structure
        # but we use it read-only for metadata extraction
        dataset = pydicom.dcmread(str(file_path), force=True)
        return dataset
    except InvalidDICOMError as e:
        logger.error(f"Invalid DICOM file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing DICOM file {file_path}: {e}")
        return None


async def parse_dicom_metadata_async(file_path: Path) -> Optional[Dataset]:
    """Async wrapper for parse_dicom_metadata.
    
    Args:
        file_path: Path to the DICOM file
    
    Returns:
        pydicom Dataset object, or None if parsing fails
    """
    import asyncio
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, parse_dicom_metadata, file_path)


def get_dicom_tags(dataset: Dataset, *tags: str) -> dict:
    """Extract specific tags from a DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        *tags: Tag names or numbers to extract (e.g., "PatientID", "StudyInstanceUID")
    
    Returns:
        Dictionary mapping tag names to values
    """
    result = {}
    for tag in tags:
        try:
            if hasattr(dataset, tag):
                value = getattr(dataset, tag, None)
                if value is not None:
                    # Convert pydicom data elements to Python types
                    if hasattr(value, "value"):
                        result[tag] = value.value
                    else:
                        result[tag] = value
        except Exception as e:
            logger.debug(f"Error extracting tag {tag}: {e}")
            result[tag] = None
    return result


def verify_byte_equality(file1: Path, file2: Path) -> Tuple[bool, Optional[str]]:
    """Verify that two DICOM files are byte-for-byte identical.
    
    This is used in tests to ensure that forwarding preserves the exact bytes.
    
    Args:
        file1: Path to first file
        file2: Path to second file
    
    Returns:
        Tuple of (are_identical, error_message)
    """
    try:
        data1 = read_dicom_bytes_sync(file1)
        data2 = read_dicom_bytes_sync(file2)
        
        if len(data1) != len(data2):
            return (
                False,
                f"File sizes differ: {len(data1)} vs {len(data2)} bytes",
            )
        
        if data1 != data2:
            # Find first difference
            for i, (b1, b2) in enumerate(zip(data1, data2)):
                if b1 != b2:
                    return (
                        False,
                        f"Files differ at byte {i}: 0x{b1:02x} vs 0x{b2:02x}",
                    )
        
        return (True, None)
    except Exception as e:
        return (False, f"Error comparing files: {str(e)}")

