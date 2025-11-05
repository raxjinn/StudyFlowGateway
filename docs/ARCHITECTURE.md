# DICOM Gateway Architecture

This document describes the architecture of the DICOM Gateway system, including components, data flow, and system design.

## System Overview

The DICOM Gateway is a lightweight, HIPAA-compliant Linux-based system for receiving and forwarding DICOM studies with byte-preserving integrity. It consists of multiple independently scalable worker systems, a REST API, and a modern web interface.

## Architecture Diagram

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DICOM Gateway System                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐    │
│  │   DICOM      │         │   REST API   │         │   Web UI     │    │
│  │   Clients    │────────▶│   (FastAPI)  │◀────────│  (Vue.js)    │    │
│  │              │         │              │         │              │    │
│  └──────────────┘         └──────────────┘         └──────────────┘    │
│         │                        │                        │              │
│         │ C-STORE                │                        │              │
│         ▼                        │                        │              │
│  ┌──────────────┐         ┌──────┴──────┐         ┌──────┴──────┐      │
│  │  C-STORE SCP │         │  PostgreSQL │         │   Nginx     │      │
│  │  (Receiver)  │────────▶│   Database  │◀────────│ (Reverse    │      │
│  │              │         │             │         │   Proxy)    │      │
│  └──────────────┘         └─────────────┘         └─────────────┘      │
│         │                        │                                      │
│         │                        │                                      │
│         ▼                        ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │                    Worker Services                           │       │
│  │                                                              │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │       │
│  │  │    Queue     │  │  Forwarding  │  │   DB Pool    │      │       │
│  │  │   Worker     │  │   Worker     │  │   Worker     │      │       │
│  │  │              │  │              │  │              │      │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │       │
│  │         │                  │                  │             │       │
│  │         └──────────────────┼──────────────────┘             │       │
│  │                            │                                │       │
│  │                            ▼                                │       │
│  │                    ┌──────────────┐                         │       │
│  │                    │ C-STORE SCU  │                         │       │
│  │                    │ (Forwarder)  │                         │       │
│  │                    └──────────────┘                         │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                           │
│                            ┌──────────────┐                              │
│                            │   Storage    │                              │
│                            │  Filesystem  │                              │
│                            │ /var/lib/... │                              │
│                            └──────────────┘                              │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. DICOM C-STORE SCP (Receiver)

**Purpose**: Receives DICOM C-STORE requests from external systems

**Responsibilities**:
- Accept incoming DICOM C-STORE associations
- Receive DICOM files with byte-preserving integrity
- Store files to filesystem
- Queue files for processing
- Record ingest events

**Key Features**:
- Byte-preserving file storage (128-byte preamble + DICM prefix)
- Multiple SOP class support
- Configurable AE Title and port
- TLS support
- Metrics collection

**Technology**: pynetdicom

### 2. REST API (FastAPI)

**Purpose**: Provides RESTful API for system management and monitoring

**Responsibilities**:
- User authentication and authorization
- Study management endpoints
- Destination configuration
- Queue management
- Metrics and monitoring
- Configuration management
- Audit log access

**Key Features**:
- JWT-based authentication
- Role-based access control (RBAC)
- OpenAPI/Swagger documentation
- Prometheus metrics export
- Health check endpoints

**Technology**: FastAPI, SQLAlchemy, asyncpg

### 3. Web UI (Vue.js)

**Purpose**: Modern web interface for system management

**Responsibilities**:
- User authentication
- Dashboard with metrics
- Study browsing and management
- Destination configuration
- Queue monitoring
- Settings management

**Key Features**:
- Responsive design
- Real-time updates
- Dark mode support
- Accessible UI

**Technology**: Vue.js 3, Vite, Tailwind CSS, Pinia

### 4. PostgreSQL Database

**Purpose**: Central data store for metadata, queue, and audit logs

**Responsibilities**:
- Store study, series, instance metadata
- Job queue management
- Destination configuration
- User accounts and authentication
- Audit logs
- Metrics rollup

**Key Features**:
- ACID compliance
- Connection pooling
- LISTEN/NOTIFY for real-time notifications
- pgcrypto for encryption at rest
- Full-text search support

**Technology**: PostgreSQL 14+, asyncpg

### 5. Queue Worker

**Purpose**: Processes received DICOM files and creates forwarding jobs

**Responsibilities**:
- Process jobs from queue
- Parse DICOM metadata
- Create study/series/instance records
- Queue forwarding jobs based on rules
- Handle errors and retries

**Key Features**:
- Concurrent job processing
- Configurable concurrency
- Retry logic
- Error handling

**Technology**: Python asyncio, SQLAlchemy

### 6. Forwarding Worker

**Purpose**: Forwards DICOM studies to configured destinations

**Responsibilities**:
- Process forward jobs from queue
- Forward files via C-STORE SCU
- Handle retries and failures
- Update job status
- Record forwarding metrics

**Key Features**:
- Exponential backoff retry
- Multiple destination support
- TLS support
- Connection pooling
- Dead-letter queue

**Technology**: pynetdicom, Python asyncio

### 7. DB Pool Worker

**Purpose**: Batches database writes for performance

**Responsibilities**:
- Batch insert ingest events
- Batch insert metrics
- Optimize database writes
- Reduce database load

**Key Features**:
- Configurable batch size
- Time-based flushing
- Error handling

**Technology**: asyncpg, SQLAlchemy

### 8. C-STORE SCU (Forwarder)

**Purpose**: Sends DICOM C-STORE requests to remote systems

**Responsibilities**:
- Establish DICOM associations
- Send files with byte-preserving integrity
- Handle responses
- Error handling

**Key Features**:
- Byte-preserving transmission
- TLS support
- Configurable timeouts
- Metrics collection

**Technology**: pynetdicom

### 9. Nginx Reverse Proxy

**Purpose**: HTTPS termination and reverse proxy

**Responsibilities**:
- SSL/TLS termination
- Reverse proxy to FastAPI
- Static file serving (Vue.js)
- Rate limiting
- Security headers

**Key Features**:
- Let's Encrypt support
- HSTS
- Modern cipher suites
- Gzip compression

**Technology**: Nginx

## Data Flow

### Receiving a DICOM Study

```
1. External System → C-STORE SCP (Port 104)
   ├─ Receives DICOM file
   ├─ Validates file structure
   └─ Stores file with byte preservation

2. C-STORE SCP → Filesystem
   ├─ Writes to /var/lib/dicom-gw/storage/incoming/
   └─ Preserves 128-byte preamble + DICM prefix

3. C-STORE SCP → PostgreSQL Queue
   ├─ Creates job in forward_jobs table
   └─ Status: "pending"

4. PostgreSQL → Queue Worker (via LISTEN/NOTIFY)
   ├─ Worker picks up job
   ├─ Parses DICOM metadata
   ├─ Creates study/series/instance records
   └─ Creates forwarding jobs for each destination

5. Queue Worker → PostgreSQL
   ├─ Updates job status to "processing"
   ├─ Inserts metadata records
   └─ Creates forward_jobs entries
```

### Forwarding a DICOM Study

```
1. Forwarding Worker → PostgreSQL Queue
   ├─ Polls for pending forward jobs
   └─ Uses SELECT FOR UPDATE SKIP LOCKED

2. Forwarding Worker → Filesystem
   ├─ Reads DICOM file from storage
   └─ Validates byte integrity

3. Forwarding Worker → C-STORE SCU
   ├─ Establishes association with remote AE
   └─ Sends file with byte preservation

4. C-STORE SCU → Remote DICOM System
   ├─ C-STORE request
   └─ Waits for response

5. Forwarding Worker → PostgreSQL
   ├─ Updates job status (success/failed)
   ├─ Records metrics
   └─ Handles retries if failed
```

### User Access Flow

```
1. User → Web UI (Browser)
   ├─ Opens https://gateway.example.com
   └─ Login page

2. Web UI → REST API
   ├─ POST /api/v1/auth/login
   └─ Receives JWT token

3. Web UI → REST API (with JWT)
   ├─ GET /api/v1/studies
   ├─ GET /api/v1/metrics
   └─ Other endpoints

4. REST API → PostgreSQL
   ├─ Validates JWT token
   ├─ Checks RBAC permissions
   ├─ Queries database
   └─ Returns results

5. REST API → Web UI
   ├─ JSON responses
   └─ Web UI renders data
```

## Scalability

### Horizontal Scaling

The system is designed for horizontal scaling:

- **C-STORE SCP**: Can run multiple instances (load balanced)
- **REST API**: Can run multiple instances (load balanced via Nginx)
- **Queue Worker**: Can run multiple instances (concurrent job processing)
- **Forwarding Worker**: Can run multiple instances (concurrent forwarding)
- **DB Pool Worker**: Can run multiple instances (shared database)

### Vertical Scaling

- **Database Connection Pool**: Configurable min/max connections
- **Worker Concurrency**: Configurable concurrent jobs per worker
- **Batch Sizes**: Configurable batch sizes for database writes

## Security Architecture

### Authentication & Authorization

- **JWT Tokens**: Stateless authentication
- **Argon2id**: Password hashing
- **RBAC**: Role-based access control
- **Session Management**: Configurable timeouts

### Encryption

- **TLS/SSL**: HTTPS for web interface
- **DICOM TLS**: Optional TLS for DICOM communication
- **Encryption at Rest**: pgcrypto for sensitive fields
- **LUKS**: Optional full-disk encryption

### Audit Logging

- **Append-Only**: Immutable audit logs
- **Comprehensive**: All admin actions logged
- **Searchable**: Full-text search support
- **Retention**: Configurable retention policies

## Deployment Architecture

### Single Server Deployment

```
┌─────────────────────────────────────┐
│         Single Server               │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │  Nginx   │  │ FastAPI  │        │
│  │   :443   │─▶│   :8000  │        │
│  └──────────┘  └──────────┘        │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │ C-STORE  │  │ Workers  │        │
│  │  SCP     │  │  (x3)    │        │
│  │   :104   │  └──────────┘        │
│  └──────────┘        │              │
│         │            │              │
│         └────────────┼──────────────┘
│                      │
│              ┌───────▼──────┐
│              │  PostgreSQL  │
│              │   :5432      │
│              └──────────────┘
│
│  Storage: /var/lib/dicom-gw/
└─────────────────────────────────────┘
```

### Distributed Deployment

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Load        │     │  API Server  │     │  API Server  │
│  Balancer    │────▶│  (FastAPI)   │     │  (FastAPI)   │
│  (Nginx)     │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
      │                      │                      │
      │                      └──────────┬───────────┘
      │                                 │
      ▼                                 ▼
┌──────────────┐              ┌──────────────┐
│ DICOM SCP    │              │  PostgreSQL  │
│  Server      │              │   Cluster    │
│              │              │              │
└──────────────┘              └──────────────┘
      │                                 │
      │                      ┌──────────┴──────────┐
      │                      │                     │
      ▼                      ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Queue        │    │ Forwarding   │    │ DB Pool      │
│ Worker       │    │ Worker       │    │ Worker       │
│ (x2)         │    │ (x4)         │    │ (x2)         │
└──────────────┘    └──────────────┘    └──────────────┘
      │                      │                     │
      └──────────────────────┼─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Shared Storage │
                    │  (NFS/Gluster)  │
                    └─────────────────┘
```

## Technology Stack

### Backend
- **Python 3.11+**: Core language
- **FastAPI**: REST API framework
- **SQLAlchemy**: ORM
- **asyncpg**: Async PostgreSQL driver
- **pynetdicom**: DICOM networking
- **pydicom**: DICOM file handling

### Frontend
- **Vue.js 3**: UI framework
- **Vite**: Build tool
- **Tailwind CSS**: Styling
- **Pinia**: State management
- **Axios**: HTTP client

### Infrastructure
- **PostgreSQL 14+**: Database
- **Nginx**: Reverse proxy
- **systemd**: Service management
- **certbot**: TLS certificates

### Monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization (optional)

## Performance Characteristics

### Throughput
- **Receive**: 10+ files/second (configurable)
- **Forward**: 5+ files/second per destination
- **Concurrent**: 15+ files/second with multiple workers

### Latency
- **Receive**: < 1000ms (mean)
- **Forward**: < 2000ms (mean)
- **File I/O**: < 10ms (read), < 50ms (write)

### Scalability
- **Horizontal**: Linear scaling with worker instances
- **Database**: Connection pooling and async operations
- **Storage**: Configurable paths and cleanup policies

## Error Handling

### Retry Logic
- **Exponential Backoff**: Configurable retry delays
- **Max Retries**: Configurable per destination
- **Dead-Letter Queue**: Failed jobs after max retries

### Error Recovery
- **Automatic Retries**: Configurable retry policies
- **Manual Retry**: API endpoint for retrying jobs
- **Replay**: Ability to replay studies

## Monitoring & Observability

### Metrics
- **Prometheus Export**: Comprehensive metrics
- **Queue Depth**: Real-time queue monitoring
- **Worker Stats**: Per-worker metrics
- **SCP/SCU Stats**: DICOM operation metrics

### Logging
- **Structured Logging**: JSON format
- **Log Levels**: Configurable per component
- **Audit Logs**: Comprehensive audit trail
- **Log Rotation**: Automatic log management

### Health Checks
- **Liveness Probe**: Service availability
- **Readiness Probe**: Service readiness
- **Health Endpoint**: Comprehensive health status

