# Configuration Guide

This guide covers configuration options for the DICOM Gateway.

## Configuration Methods

The DICOM Gateway supports multiple configuration methods:

1. **YAML Configuration File** (recommended): `/etc/dicom-gw/config.yaml`
2. **Environment Variables**: Override YAML settings
3. **Command Line Arguments**: Override specific settings

Priority order: Environment Variables > YAML File > Defaults

## Configuration File

The main configuration file is located at `/etc/dicom-gw/config.yaml`.

### Example Configuration

```yaml
application:
  name: "DICOM Gateway"
  debug: false
  host: "0.0.0.0"
  port: 8000
  api_prefix: "/api/v1"
  secret_key: "your-secret-key-here"
  jwt_secret_key: "your-jwt-secret-key-here"
  jwt_expiration_hours: 24
  log_level: "INFO"

database:
  url: "postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gateway"
  pool_min: 5
  pool_max: 20
  pool_acquire_timeout: 30

dicom:
  ae_title: "GATEWAY_AE"
  port: 104
  max_pdu: 16384
  storage:
    incoming_path: "/var/lib/dicom-gw/storage/incoming"
    queue_path: "/var/lib/dicom-gw/storage/queue"
    forwarded_path: "/var/lib/dicom-gw/storage/forwarded"
    failed_path: "/var/lib/dicom-gw/storage/failed"
    tmp_path: "/var/lib/dicom-gw/storage/tmp"

security:
  password_min_length: 8
  password_require_uppercase: true
  password_require_lowercase: true
  password_require_numbers: true
  password_require_special: false
  session_timeout_minutes: 60

workers:
  queue_worker:
    enabled: true
    concurrency: 4
    poll_interval: 1.0
    batch_size: 100
  
  forwarder_worker:
    enabled: true
    concurrency: 4
    poll_interval: 1.0
    max_retries: 3
    retry_delay: 60
  
  dbpool_worker:
    enabled: true
    batch_size: 1000
    flush_interval: 5.0

destinations:
  - name: "Primary PACS"
    ae_title: "PACS_AE"
    host: "pacs.example.com"
    port: 104
    enabled: true
    max_pdu: 16384
    timeout: 30
    tls_enabled: false
```

## Configuration Sections

### Application Settings

```yaml
application:
  name: "DICOM Gateway"              # Application name
  debug: false                        # Debug mode (enable detailed logging)
  host: "0.0.0.0"                    # Bind address
  port: 8000                          # API port
  api_prefix: "/api/v1"              # API path prefix
  secret_key: "..."                   # Secret key for encryption
  jwt_secret_key: "..."               # JWT signing key
  jwt_expiration_hours: 24            # JWT token expiration
  log_level: "INFO"                   # Logging level (DEBUG, INFO, WARNING, ERROR)
```

**Environment Variables:**
- `DICOM_GW_APP_NAME`
- `DICOM_GW_APP_DEBUG`
- `DICOM_GW_APP_HOST`
- `DICOM_GW_APP_PORT`
- `DICOM_GW_APP_SECRET_KEY`
- `DICOM_GW_JWT_SECRET_KEY`
- `DICOM_GW_JWT_EXPIRATION_HOURS`
- `DICOM_GW_LOG_LEVEL`

### Database Configuration

```yaml
database:
  url: "postgresql+asyncpg://user:pass@host:port/db"
  pool_min: 5                         # Minimum connection pool size
  pool_max: 20                        # Maximum connection pool size
  pool_acquire_timeout: 30            # Connection acquisition timeout (seconds)
```

**Environment Variables:**
- `DICOM_GW_DATABASE_URL`
- `DICOM_GW_DATABASE_POOL_MIN`
- `DICOM_GW_DATABASE_POOL_MAX`
- `DICOM_GW_DATABASE_POOL_ACQUIRE_TIMEOUT`

**Database URL Format:**
- PostgreSQL with asyncpg: `postgresql+asyncpg://user:password@host:port/database`
- PostgreSQL with psycopg: `postgresql://user:password@host:port/database`

### DICOM Configuration

```yaml
dicom:
  ae_title: "GATEWAY_AE"              # Application Entity Title
  port: 104                            # DICOM C-STORE port
  max_pdu: 16384                       # Maximum PDU size
  storage:
    incoming_path: "/var/lib/dicom-gw/storage/incoming"
    queue_path: "/var/lib/dicom-gw/storage/queue"
    forwarded_path: "/var/lib/dicom-gw/storage/forwarded"
    failed_path: "/var/lib/dicom-gw/storage/failed"
    tmp_path: "/var/lib/dicom-gw/storage/tmp"
```

**Environment Variables:**
- `DICOM_GW_DICOM_AE_TITLE`
- `DICOM_GW_DICOM_PORT`
- `DICOM_GW_DICOM_MAX_PDU`
- `DICOM_GW_DICOM_INCOMING_PATH`
- `DICOM_GW_DICOM_QUEUE_PATH`
- `DICOM_GW_DICOM_FORWARDED_PATH`
- `DICOM_GW_DICOM_FAILED_PATH`
- `DICOM_GW_DICOM_TMP_PATH`

### Security Settings

```yaml
security:
  password_min_length: 8
  password_require_uppercase: true
  password_require_lowercase: true
  password_require_numbers: true
  password_require_special: false
  session_timeout_minutes: 60
```

**Environment Variables:**
- `DICOM_GW_PASSWORD_MIN_LENGTH`
- `DICOM_GW_PASSWORD_REQUIRE_UPPERCASE`
- `DICOM_GW_PASSWORD_REQUIRE_LOWERCASE`
- `DICOM_GW_PASSWORD_REQUIRE_NUMBERS`
- `DICOM_GW_PASSWORD_REQUIRE_SPECIAL`
- `DICOM_GW_SESSION_TIMEOUT_MINUTES`

### Worker Configuration

```yaml
workers:
  queue_worker:
    enabled: true
    concurrency: 4                     # Number of concurrent jobs
    poll_interval: 1.0                 # Poll interval (seconds)
    batch_size: 100                    # Batch size for processing
  
  forwarder_worker:
    enabled: true
    concurrency: 4
    poll_interval: 1.0
    max_retries: 3                     # Maximum retry attempts
    retry_delay: 60                    # Retry delay (seconds)
  
  dbpool_worker:
    enabled: true
    batch_size: 1000                   # Batch size for database writes
    flush_interval: 5.0                # Flush interval (seconds)
```

**Environment Variables:**
- `DICOM_GW_QUEUE_WORKER_ENABLED`
- `DICOM_GW_QUEUE_WORKER_CONCURRENCY`
- `DICOM_GW_FORWARDER_WORKER_ENABLED`
- `DICOM_GW_FORWARDER_WORKER_MAX_RETRIES`
- `DICOM_GW_DBPOOL_WORKER_BATCH_SIZE`

### Destination Configuration

Destinations can be configured in the YAML file or via the API:

```yaml
destinations:
  - name: "Primary PACS"
    ae_title: "PACS_AE"
    host: "pacs.example.com"
    port: 104
    enabled: true
    max_pdu: 16384
    timeout: 30
    connection_timeout: 10
    tls_enabled: false
    tls_cert_path: null
    tls_key_path: null
    tls_ca_path: null
    tls_no_verify: false
    forwarding_rules: null
    description: "Primary PACS system"
```

**Destination Settings:**
- `name`: Human-readable name
- `ae_title`: Remote Application Entity Title
- `host`: Remote hostname or IP address
- `port`: Remote DICOM port (default: 104)
- `enabled`: Enable/disable destination
- `max_pdu`: Maximum PDU size
- `timeout`: Operation timeout (seconds)
- `connection_timeout`: Connection timeout (seconds)
- `tls_enabled`: Enable TLS encryption
- `tls_cert_path`: Path to client certificate
- `tls_key_path`: Path to client private key
- `tls_ca_path`: Path to CA certificate
- `tls_no_verify`: Disable certificate verification (not recommended)
- `forwarding_rules`: JSON object with forwarding rules
- `description`: Optional description

## Reloading Configuration

### Via API

```bash
curl -X POST https://your-server/api/v1/config/reload \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Via Systemd

```bash
sudo systemctl reload dicom-gw-api.service
```

### Manual Reload

Most settings require a service restart:

```bash
sudo systemctl restart dicom-gateway.target
```

## Configuration Validation

Validate configuration before applying:

```bash
sudo -u dicom-gw python -c "
from dicom_gw.config.yaml_config import get_config_manager
try:
    config = get_config_manager().get_config()
    print('Configuration is valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

## Secure Configuration

### Sensitive Values

Never commit sensitive values to version control:

1. **Use environment variables** for secrets:
   ```bash
   export DICOM_GW_DATABASE_PASSWORD="secure-password"
   export DICOM_GW_APP_SECRET_KEY="secure-secret-key"
   ```

2. **Set file permissions**:
   ```bash
   sudo chmod 600 /etc/dicom-gw/config.yaml
   sudo chmod 600 /etc/dicom-gw/environment
   ```

3. **Use encryption at rest**:
   - Enable LUKS for storage volumes
   - Use pgcrypto for sensitive database fields

### Secret Key Generation

Generate secure secret keys:

```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate encryption key
python -c "import secrets; print(secrets.token_hex(32))"
```

## Configuration Examples

### Development Configuration

```yaml
application:
  debug: true
  log_level: "DEBUG"

database:
  url: "postgresql+asyncpg://dicom_gw:dev@localhost:5432/dicom_gateway_dev"

dicom:
  ae_title: "DEV_GATEWAY"
  port: 10404  # Use non-standard port for development
```

### Production Configuration

```yaml
application:
  debug: false
  log_level: "INFO"
  host: "127.0.0.1"  # Bind to localhost, use Nginx reverse proxy

database:
  url: "postgresql+asyncpg://dicom_gw:password@db.example.com:5432/dicom_gateway"
  pool_min: 10
  pool_max: 50

dicom:
  ae_title: "PROD_GATEWAY"
  port: 104

security:
  password_min_length: 12
  password_require_special: true
  session_timeout_minutes: 30
```

### High-Throughput Configuration

```yaml
workers:
  queue_worker:
    concurrency: 8
    batch_size: 500
  
  forwarder_worker:
    concurrency: 8
    poll_interval: 0.5
  
  dbpool_worker:
    batch_size: 5000
    flush_interval: 2.0

database:
  pool_min: 10
  pool_max: 50
```

## Troubleshooting

### Configuration Not Loading

1. Check file permissions:
   ```bash
   ls -la /etc/dicom-gw/config.yaml
   ```

2. Check YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('/etc/dicom-gw/config.yaml'))"
   ```

3. Check logs:
   ```bash
   sudo journalctl -u dicom-gw-api.service -n 50
   ```

### Environment Variables Not Applied

1. Verify environment file:
   ```bash
   cat /etc/dicom-gw/environment
   ```

2. Check service environment:
   ```bash
   sudo systemctl show dicom-gw-api.service | grep Environment
   ```

3. Restart services:
   ```bash
   sudo systemctl restart dicom-gateway.target
   ```

## Next Steps

- Setup [TLS/SSL Certificates](TLS_SETUP.md)
- Configure [Monitoring](MONITORING.md)
- Review [Operations Guide](OPERATIONS.md)

