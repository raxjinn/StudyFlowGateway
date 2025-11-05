# DICOM Gateway - Master Task List

## Project Overview
Build a lightweight Linux DICOM Gateway with Python backend, Vue.js frontend, Nginx, PostgreSQL, and RPM packaging. The system must preserve DICOM binary integrity (128-byte preamble + DICM prefix) and handle high-throughput receiving/forwarding.

---

## Setup & Infrastructure

- [ ] **Task 1:** Project setup: Initialize Python project structure with virtual environment, requirements.txt, and directory layout
- [ ] **Task 2:** Create PostgreSQL database schema: Define tables (studies, series, instances, ingest_events, forward_jobs, destinations, audit_logs, metrics_rollup) with indexes
- [ ] **Task 3:** Set up database migrations: Create Alembic configuration and initial migration scripts
- [ ] **Task 4:** Create storage layout scripts: Implement directory structure creation with correct permissions in /var/lib/dicom-gw/

## Core DICOM Processing

- [ ] **Task 5:** Implement byte-preserving DICOM I/O module: Create functions to read/write DICOM files preserving 128-byte preamble and DICM prefix
- [ ] **Task 6:** Create DICOM Storage SCP receiver: Implement C-STORE receiver using pynetdicom with byte-preserving file storage
- [ ] **Task 7:** Implement DICOM Storage SCU forwarder: Create C-STORE client for forwarding studies with byte-preserving transmission

## Database & Queue

- [ ] **Task 8:** Build PostgreSQL connection pool module: Implement async connection pooling with psycopg3/asyncpg, prepared statements, and batch operations
- [ ] **Task 9:** Create queue system: Implement PostgreSQL-backed job queue with SKIP LOCKED pattern and LISTEN/NOTIFY

## Worker Services

- [ ] **Task 10:** Implement Queue Worker service: Create worker that processes job queue events and orchestrates tasks
- [ ] **Task 11:** Implement Forwarding Worker service: Create worker that forwards studies to configured AEs with retry logic
- [ ] **Task 12:** Implement DB Pool Worker service: Create worker for asynchronous database writes with batch operations

## API & Security

- [ ] **Task 13:** Build REST API layer: Create FastAPI/Flask application with endpoints for health, metrics, studies, destinations, queues
- [ ] **Task 14:** Implement authentication and RBAC: Add username/password auth with argon2id, session management, and role-based access
- [ ] **Task 15:** Create audit logging system: Implement append-only audit table and logging for all admin actions
- [ ] **Task 16:** Implement metrics and telemetry: Add Prometheus-style metrics for throughput, latency, queue depth, and forwarding stats

## Frontend

- [ ] **Task 17:** Build Vue.js frontend: Create Vue 3 + Vite application with dashboard, studies list, destinations, queues, settings pages

## Configuration & Deployment

- [ ] **Task 18:** Create configuration management: Implement YAML-based config system for app, database, and AE settings
- [ ] **Task 19:** Implement encryption at rest: Add LUKS documentation and pgcrypto support for sensitive fields
- [ ] **Task 20:** Create TLS/SSL automation: Implement Let's Encrypt provisioning and certificate upload functionality
- [ ] **Task 21:** Configure Nginx reverse proxy: Create Nginx config with HTTPS, modern ciphers, HSTS, and reverse proxy to backend
- [ ] **Task 22:** Create systemd service files: Write unit files for API, Queue Worker, Forwarding Worker, and DB Pool Worker
- [ ] **Task 23:** Build RPM spec file: Create RPM specification with pre/post install scripts, file layouts, and dependencies

## Testing

- [ ] **Task 24:** Write unit tests: Create tests for byte-preserving I/O, DICOM parsing, and database operations
- [ ] **Task 25:** Write integration tests: Create tests for C-STORE receive/forward with byte-for-byte verification
- [ ] **Task 26:** Create load tests: Implement tests for throughput, latency, and database pool saturation

## Documentation

- [ ] **Task 27:** Generate OpenAPI specification: Create YAML spec for all API endpoints
- [ ] **Task 28:** Write admin documentation: Create install guide, configuration docs, TLS setup, and operations runbooks
- [ ] **Task 29:** Create architecture diagram: Generate visual diagram showing system components and data flow

---

## Progress Tracking
- **Total Tasks:** 29
- **Completed:** 0
- **In Progress:** 1
- **Remaining:** 28

