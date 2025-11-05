"""SQLAlchemy models for DICOM Gateway database schema."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


class Base(DeclarativeBase):
    """Base class for all database models."""


class Study(Base):
    """DICOM Study table."""
    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_instance_uid: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    patient_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    patient_name: Mapped[Optional[str]] = mapped_column(String(255))
    patient_birth_date: Mapped[Optional[str]] = mapped_column(String(10))
    patient_sex: Mapped[Optional[str]] = mapped_column(String(1))
    study_date: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    study_time: Mapped[Optional[str]] = mapped_column(String(14))
    accession_number: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    study_description: Mapped[Optional[str]] = mapped_column(String(255))
    referring_physician_name: Mapped[Optional[str]] = mapped_column(String(255))
    modality: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    institution_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Metadata
    status: Mapped[str] = mapped_column(
        String(50), default="received", index=True
    )  # received, processing, forwarded, failed
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024))
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    forwarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    series: Mapped[list["Series"]] = relationship(
        "Series", back_populates="study", cascade="all, delete-orphan"
    )
    ingest_events: Mapped[list["IngestEvent"]] = relationship(
        "IngestEvent", back_populates="study"
    )
    forward_jobs: Mapped[list["ForwardJob"]] = relationship(
        "ForwardJob", back_populates="study"
    )

    __table_args__ = (
        Index("idx_study_status_created", "status", "created_at"),
        Index("idx_study_patient_date", "patient_id", "study_date"),
    )


class Series(Base):
    """DICOM Series table."""
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    series_instance_uid: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    series_number: Mapped[Optional[int]] = mapped_column(Integer)
    series_date: Mapped[Optional[str]] = mapped_column(String(10))
    series_time: Mapped[Optional[str]] = mapped_column(String(14))
    modality: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    series_description: Mapped[Optional[str]] = mapped_column(String(255))
    body_part_examined: Mapped[Optional[str]] = mapped_column(String(255))
    protocol_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Metadata
    instance_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    study: Mapped["Study"] = relationship("Study", back_populates="series")
    instances: Mapped[list["Instance"]] = relationship(
        "Instance", back_populates="series", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_series_study_modality", "study_id", "modality"),
    )


class Instance(Base):
    """DICOM Instance (SOP Instance) table."""
    __tablename__ = "instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False
    )
    sop_instance_uid: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    sop_class_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_number: Mapped[Optional[int]] = mapped_column(Integer)
    content_date: Mapped[Optional[str]] = mapped_column(String(10))
    content_time: Mapped[Optional[str]] = mapped_column(String(14))
    
    # File metadata
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transfer_syntax_uid: Mapped[Optional[str]] = mapped_column(String(255))
    has_preamble: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    series: Mapped["Series"] = relationship("Series", back_populates="instances")

    __table_args__ = (
        Index("idx_instance_series_created", "series_id", "created_at"),
    )


class IngestEvent(Base):
    """Event log for DICOM ingestion (receipt)."""
    __tablename__ = "ingest_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id", ondelete="SET NULL")
    )
    sop_instance_uid: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Source information
    calling_ae_title: Mapped[Optional[str]] = mapped_column(String(255))
    called_ae_title: Mapped[Optional[str]] = mapped_column(String(255))
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 compatible
    
    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # received, stored, failed
    status: Mapped[str] = mapped_column(
        String(50), default="success", index=True
    )  # success, failed, warning
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Performance metrics
    receive_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    storage_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    # Relationships
    study: Mapped[Optional["Study"]] = relationship("Study", back_populates="ingest_events")

    __table_args__ = (
        Index("idx_ingest_created_type", "created_at", "event_type"),
        Index("idx_ingest_status_created", "status", "created_at"),
    )


class ForwardJob(Base):
    """Job queue for forwarding studies to remote AEs."""
    __tablename__ = "forward_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    
    # Job status
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # pending, processing, completed, failed, dead_letter
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    
    # Scheduling
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Results
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Performance metrics
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    instances_sent: Mapped[int] = mapped_column(Integer, default=0)
    instances_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    study: Mapped["Study"] = relationship("Study", back_populates="forward_jobs")
    destination: Mapped["Destination"] = relationship("Destination", back_populates="forward_jobs")

    __table_args__ = (
        Index("idx_forward_job_status_available", "status", "available_at"),
        Index("idx_forward_job_priority_available", "priority", "available_at"),
        CheckConstraint("attempts >= 0", name="forward_job_attempts_non_negative"),
        CheckConstraint("max_attempts > 0", name="forward_job_max_attempts_positive"),
    )


class Destination(Base):
    """Configured DICOM Application Entity (AE) destinations."""
    __tablename__ = "destinations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    ae_title: Mapped[str] = mapped_column(String(255), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Connection settings
    max_pdu: Mapped[int] = mapped_column(Integer, default=16384)
    timeout: Mapped[int] = mapped_column(Integer, default=30)
    connection_timeout: Mapped[int] = mapped_column(Integer, default=10)
    
    # TLS settings
    tls_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tls_cert_path: Mapped[Optional[str]] = mapped_column(String(1024))
    tls_key_path: Mapped[Optional[str]] = mapped_column(String(1024))
    tls_ca_path: Mapped[Optional[str]] = mapped_column(String(1024))
    tls_no_verify: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    
    # Forwarding rules (JSON)
    forwarding_rules: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    forward_jobs: Mapped[list["ForwardJob"]] = relationship(
        "ForwardJob", back_populates="destination"
    )

    __table_args__ = (
        Index("idx_destination_enabled", "enabled"),
        CheckConstraint("port > 0 AND port < 65536", name="destination_port_valid"),
        CheckConstraint("timeout > 0", name="destination_timeout_positive"),
    )


class AuditLog(Base):
    """Append-only audit log for security and compliance."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Actor information
    user_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100))
    resource_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Result
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # success, failure, denied
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Additional context (JSON)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_created_action", "created_at", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


class Job(Base):
    """Generic job queue for asynchronous processing."""
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Job identification
    job_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # process_received_file, extract_metadata, etc.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Job status
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # pending, processing, completed, failed, dead_letter
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    
    # Scheduling
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Worker tracking
    worker_id: Mapped[Optional[str]] = mapped_column(String(255))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Results
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    retry_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_job_status_available", "status", "available_at"),
        Index("idx_job_priority_available", "priority", "available_at"),
        Index("idx_job_type_status", "job_type", "status"),
        CheckConstraint("attempts >= 0", name="job_attempts_non_negative"),
        CheckConstraint("max_attempts > 0", name="job_max_attempts_positive"),
    )


class MetricsRollup(Base):
    """Time-series metrics for monitoring and dashboards."""
    __tablename__ = "metrics_rollup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Time bucket
    bucket_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    bucket_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metric name and value
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(BigInteger)  # Can store integers or floats
    metric_type: Mapped[str] = mapped_column(
        String(50), default="counter"
    )  # counter, gauge, histogram
    
    # Labels/dimensions (JSON)
    labels: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_metrics_bucket_name", "bucket_start", "metric_name"),
        Index("idx_metrics_name_bucket", "metric_name", "bucket_start"),
    )


class User(Base):
    """User accounts for authentication and authorization."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    
    # Password (hashed with argon2id)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Role-based access control
    role: Mapped[str] = mapped_column(
        String(50), default="user", nullable=False, index=True
    )  # admin, operator, user, viewer
    
    # Account status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Metadata
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_user_role_enabled", "role", "enabled"),
        CheckConstraint("failed_login_attempts >= 0", name="user_failed_logins_non_negative"),
    )

