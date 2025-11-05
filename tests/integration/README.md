# Integration Tests

This directory contains integration tests for the DICOM Gateway that test the full workflow including C-STORE receive and forward operations.

## Test Files

### `test_cstore_receive.py`
Tests for C-STORE receive (SCP) operations:
- Byte preservation during receive
- Multiple file reception
- File size verification
- Preamble and DICM prefix preservation

### `test_cstore_forward.py`
Tests for C-STORE forward (SCU) operations:
- Byte preservation during forward
- File size verification
- Multiple file forwarding
- Preamble and DICM prefix preservation

### `test_end_to_end.py`
End-to-end tests for complete workflows:
- Receive -> Forward workflow
- Byte preservation through entire pipeline
- Multiple files through pipeline

## Running Integration Tests

### Prerequisites

1. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Test database** (if needed):
   - Tests use in-memory SQLite for most operations
   - Some tests may require PostgreSQL

### Run All Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with markers
pytest tests/integration/ -v -m integration
```

### Run Specific Test File

```bash
# Test C-STORE receive
pytest tests/integration/test_cstore_receive.py -v

# Test C-STORE forward
pytest tests/integration/test_cstore_forward.py -v

# Test end-to-end workflow
pytest tests/integration/test_end_to_end.py -v
```

### Run Specific Test

```bash
pytest tests/integration/test_cstore_receive.py::TestCStoreReceive::test_receive_preserves_bytes -v
```

## Test Requirements

- **Network ports**: Tests use random ports (0) to avoid conflicts
- **Mock servers**: Tests create temporary SCP servers for testing
- **File system**: Tests use temporary directories
- **Async support**: Tests use pytest-asyncio for async operations

## Byte Preservation Verification

All integration tests verify:
1. **128-byte preamble**: Preserved exactly as received
2. **DICM prefix**: 4-byte "DICM" prefix preserved
3. **Complete file**: Exact byte-for-byte match
4. **File size**: Size matches original exactly

## Troubleshooting

### Port Already in Use

If tests fail with port errors:
- Tests use random ports (0) to avoid conflicts
- If issues persist, check for other DICOM servers running

### Timeout Issues

If tests timeout:
- Increase wait times in test code
- Check system resources
- Verify network connectivity

### Byte Mismatch

If byte verification fails:
- Check DICOM file format
- Verify pynetdicom configuration
- Review file I/O operations

