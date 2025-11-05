"""Pytest configuration for load tests."""

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async load tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables."""
    # Set test environment variables
    monkeypatch.setenv("DICOM_GW_APP_ENV", "test")
    monkeypatch.setenv("DICOM_GW_APP_DEBUG", "true")
    monkeypatch.setenv("DICOM_GW_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

