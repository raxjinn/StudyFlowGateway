"""Pytest configuration and shared fixtures for unit tests."""

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_dicom_path(tmp_path):
    """Create a sample DICOM file path for testing."""
    return tmp_path / "sample.dcm"

