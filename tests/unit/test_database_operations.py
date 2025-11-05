"""Unit tests for database operations."""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from dicom_gw.database.models import (
    Base,
    Study,
    Series,
    Instance,
    Destination,
    ForwardJob,
    AuditLog,
    User,
)


@pytest.fixture
async def test_db_engine():
    """Create a test database engine using SQLite in-memory."""
    # Use SQLite for testing (in-memory)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_db_engine):
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
class TestStudyOperations:
    """Test Study database operations."""
    
    async def test_create_study(self, test_session):
        """Test creating a study."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            patient_id="TEST001",
            patient_name="Test^Patient",
            study_date="20240101",
            accession_number="ACC123",
            status="received",
        )
        
        test_session.add(study)
        await test_session.commit()
        await test_session.refresh(study)
        
        assert study.id is not None
        assert study.study_instance_uid == "1.2.3.4.5"
        assert study.status == "received"
    
    async def test_query_study(self, test_session):
        """Test querying a study."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            patient_id="TEST001",
            status="received",
        )
        
        test_session.add(study)
        await test_session.commit()
        
        from sqlalchemy import select
        result = await test_session.execute(
            select(Study).where(Study.study_instance_uid == "1.2.3.4.5")
        )
        found_study = result.scalar_one_or_none()
        
        assert found_study is not None
        assert found_study.patient_id == "TEST001"
    
    async def test_update_study_status(self, test_session):
        """Test updating study status."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        
        test_session.add(study)
        await test_session.commit()
        
        study.status = "forwarded"
        study.forwarded_at = datetime.utcnow()
        await test_session.commit()
        await test_session.refresh(study)
        
        assert study.status == "forwarded"
        assert study.forwarded_at is not None


@pytest.mark.asyncio
class TestSeriesOperations:
    """Test Series database operations."""
    
    async def test_create_series(self, test_session):
        """Test creating a series."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        test_session.add(study)
        await test_session.commit()
        
        series = Series(
            study_id=study.id,
            series_instance_uid="1.2.3.4.5.1",
            modality="CT",
            series_number=1,
        )
        
        test_session.add(series)
        await test_session.commit()
        await test_session.refresh(series)
        
        assert series.id is not None
        assert series.series_instance_uid == "1.2.3.4.5.1"
        assert series.study_id == study.id


@pytest.mark.asyncio
class TestInstanceOperations:
    """Test Instance database operations."""
    
    async def test_create_instance(self, test_session):
        """Test creating an instance."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        test_session.add(study)
        await test_session.commit()
        
        series = Series(
            study_id=study.id,
            series_instance_uid="1.2.3.4.5.1",
            modality="CT",
        )
        test_session.add(series)
        await test_session.commit()
        
        instance = Instance(
            series_id=series.id,
            sop_instance_uid="1.2.3.4.5.1.1",
            file_path="/path/to/file.dcm",
            file_size_bytes=1024,
        )
        
        test_session.add(instance)
        await test_session.commit()
        await test_session.refresh(instance)
        
        assert instance.id is not None
        assert instance.sop_instance_uid == "1.2.3.4.5.1.1"
        assert instance.file_size_bytes == 1024


@pytest.mark.asyncio
class TestDestinationOperations:
    """Test Destination database operations."""
    
    async def test_create_destination(self, test_session):
        """Test creating a destination."""
        destination = Destination(
            name="Test PACS",
            ae_title="TEST_PACS",
            host="pacs.example.com",
            port=104,
            enabled=True,
        )
        
        test_session.add(destination)
        await test_session.commit()
        await test_session.refresh(destination)
        
        assert destination.id is not None
        assert destination.name == "Test PACS"
        assert destination.ae_title == "TEST_PACS"
        assert destination.enabled is True
    
    async def test_query_enabled_destinations(self, test_session):
        """Test querying enabled destinations."""
        dest1 = Destination(
            name="Enabled PACS",
            ae_title="ENABLED",
            host="pacs1.example.com",
            port=104,
            enabled=True,
        )
        dest2 = Destination(
            name="Disabled PACS",
            ae_title="DISABLED",
            host="pacs2.example.com",
            port=104,
            enabled=False,
        )
        
        test_session.add(dest1)
        test_session.add(dest2)
        await test_session.commit()
        
        from sqlalchemy import select
        result = await test_session.execute(
            select(Destination).where(Destination.enabled == True)  # noqa: E712
        )
        enabled_dests = result.scalars().all()
        
        assert len(enabled_dests) == 1
        assert enabled_dests[0].name == "Enabled PACS"


@pytest.mark.asyncio
class TestForwardJobOperations:
    """Test ForwardJob database operations."""
    
    async def test_create_forward_job(self, test_session):
        """Test creating a forward job."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        test_session.add(study)
        await test_session.commit()
        
        destination = Destination(
            name="Test PACS",
            ae_title="TEST_PACS",
            host="pacs.example.com",
            port=104,
        )
        test_session.add(destination)
        await test_session.commit()
        
        forward_job = ForwardJob(
            study_id=study.id,
            destination_id=destination.id,
            status="pending",
            max_attempts=3,
        )
        
        test_session.add(forward_job)
        await test_session.commit()
        await test_session.refresh(forward_job)
        
        assert forward_job.id is not None
        assert forward_job.status == "pending"
        assert forward_job.attempts == 0


@pytest.mark.asyncio
class TestUserOperations:
    """Test User database operations."""
    
    async def test_create_user(self, test_session):
        """Test creating a user."""
        from dicom_gw.security.auth import hash_password
        
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("testpassword123"),
            role="user",
            enabled=True,
        )
        
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.role == "user"
        assert user.enabled is True
        assert user.failed_login_attempts == 0
    
    async def test_user_password_verification(self, test_session):
        """Test user password verification."""
        from dicom_gw.security.auth import hash_password, verify_password
        
        password = "testpassword123"
        password_hash = hash_password(password)
        
        user = User(
            username="testuser",
            password_hash=password_hash,
            role="user",
        )
        
        test_session.add(user)
        await test_session.commit()
        
        # Verify password
        assert verify_password(password, user.password_hash) is True
        assert verify_password("wrongpassword", user.password_hash) is False


@pytest.mark.asyncio
class TestAuditLogOperations:
    """Test AuditLog database operations."""
    
    async def test_create_audit_log(self, test_session):
        """Test creating an audit log entry."""
        audit_log = AuditLog(
            user_id=str(uuid4()),
            username="testuser",
            ip_address="192.168.1.1",
            action="login",
            status="success",
        )
        
        test_session.add(audit_log)
        await test_session.commit()
        await test_session.refresh(audit_log)
        
        assert audit_log.id is not None
        assert audit_log.action == "login"
        assert audit_log.status == "success"
        assert audit_log.created_at is not None
    
    async def test_query_audit_logs_by_user(self, test_session):
        """Test querying audit logs by user."""
        user_id = str(uuid4())
        
        log1 = AuditLog(
            user_id=user_id,
            username="testuser",
            action="login",
            status="success",
        )
        log2 = AuditLog(
            user_id=str(uuid4()),
            username="otheruser",
            action="login",
            status="success",
        )
        
        test_session.add(log1)
        test_session.add(log2)
        await test_session.commit()
        
        from sqlalchemy import select
        result = await test_session.execute(
            select(AuditLog).where(AuditLog.user_id == user_id)
        )
        user_logs = result.scalars().all()
        
        assert len(user_logs) == 1
        assert user_logs[0].username == "testuser"


@pytest.mark.asyncio
class TestDatabaseRelationships:
    """Test database relationships."""
    
    async def test_study_series_relationship(self, test_session):
        """Test Study-Series relationship."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        test_session.add(study)
        await test_session.commit()
        
        series = Series(
            study_id=study.id,
            series_instance_uid="1.2.3.4.5.1",
            modality="CT",
        )
        test_session.add(series)
        await test_session.commit()
        
        # Refresh to load relationships
        await test_session.refresh(study)
        await test_session.refresh(series)
        
        assert series.study_id == study.id
    
    async def test_series_instance_relationship(self, test_session):
        """Test Series-Instance relationship."""
        study = Study(
            study_instance_uid="1.2.3.4.5",
            status="received",
        )
        test_session.add(study)
        await test_session.commit()
        
        series = Series(
            study_id=study.id,
            series_instance_uid="1.2.3.4.5.1",
            modality="CT",
        )
        test_session.add(series)
        await test_session.commit()
        
        instance = Instance(
            series_id=series.id,
            sop_instance_uid="1.2.3.4.5.1.1",
            file_path="/path/to/file.dcm",
        )
        test_session.add(instance)
        await test_session.commit()
        
        assert instance.series_id == series.id

