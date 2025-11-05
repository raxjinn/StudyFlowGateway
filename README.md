# DICOM Gateway

A lightweight, HIPAA-compliant DICOM gateway for receiving and forwarding medical imaging studies with high throughput and binary integrity preservation.

## Features

- **Byte-preserving DICOM handling**: Preserves 128-byte preamble and DICM prefix
- **High-performance receiving**: Async C-STORE SCP with configurable concurrency
- **Intelligent forwarding**: Configurable rules with retry logic and dead-letter queue
- **PostgreSQL backend**: Scalable queue and metadata storage with connection pooling
- **Modern web UI**: Vue.js 3 dashboard for monitoring and management
- **HIPAA compliance**: Encryption at rest, TLS, audit logging, RBAC
- **Production-ready**: RPM packaging with systemd services and Nginx integration

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, pynetdicom, asyncpg
- **Database**: PostgreSQL 14+
- **Frontend**: Vue.js 3, Vite
- **Web Server**: Nginx (reverse proxy)
- **Packaging**: RPM (RHEL/Alma/Rocky 8+)

## Quick Start

### Development Setup

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
alembic upgrade head

# Run development server
uvicorn dicom_gw.api.main:app --reload --port 8000
```

### Production Installation

```bash
# Install RPM
sudo rpm -ivh dicom-gateway-*.rpm

# Configure
sudo vi /etc/dicom-gw/app.yaml

# Start services
sudo systemctl enable dicom-gw-api dicom-gw-queue dicom-gw-forwarder dicom-gw-dbpool
sudo systemctl start dicom-gw-api dicom-gw-queue dicom-gw-forwarder dicom-gw-dbpool
```

## Project Structure

```
.
├── dicom_gw/              # Main Python package
│   ├── api/               # FastAPI application
│   ├── dicom/             # DICOM processing (byte-preserving I/O)
│   ├── workers/           # Worker services (queue, forwarder, dbpool)
│   ├── database/          # Database models, migrations, pool
│   ├── queue/             # Job queue implementation
│   ├── config/            # Configuration management
│   ├── security/          # Auth, encryption, audit
│   └── metrics/           # Prometheus metrics
├── frontend/              # Vue.js application
├── nginx/                 # Nginx configuration
├── systemd/               # Systemd service files
├── rpm/                   # RPM spec and packaging scripts
├── tests/                 # Test suite
├── docs/                  # Documentation
└── migrations/            # Alembic database migrations
```

## Configuration

Configuration files are located in `/etc/dicom-gw/` (production) or `config/` (development):

- `app.yaml` - Main application settings (ports, paths, AE titles)
- `db.yaml` - Database connection settings
- `tls/` - TLS certificates and keys

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dicom_gw --cov-report=html

# Run integration tests
pytest tests/integration/

# Run load tests
pytest tests/load/ -v
```

## License

Proprietary - Internal Use Only

## Support

See `docs/` directory for detailed documentation including:
- Installation guide
- Configuration reference
- Operations runbooks
- Troubleshooting guide

