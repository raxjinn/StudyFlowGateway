# Systemd Service Files Guide

This guide covers the systemd service files for the DICOM Gateway components.

## Overview

The DICOM Gateway consists of multiple systemd services:

1. **dicom-gw-api.service** - FastAPI REST API server
2. **dicom-gw-queue-worker.service** - Job queue processing worker
3. **dicom-gw-forwarder-worker.service** - DICOM forwarding worker
4. **dicom-gw-dbpool-worker.service** - Database batch write worker
5. **dicom-gw-scp.service** - DICOM C-STORE receiver (SCP)
6. **dicom-gw.target** - Target to start all services together

## Installation

### 1. Copy Service Files

```bash
# Copy all service files to systemd directory
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.target /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload
```

### 2. Create Service User

```bash
# Create dicom-gw user and group
sudo useradd -r -s /bin/false -d /opt/dicom-gw dicom-gw

# Create necessary directories
sudo mkdir -p /opt/dicom-gw
sudo mkdir -p /var/lib/dicom-gw
sudo mkdir -p /var/log/dicom-gw
sudo mkdir -p /etc/dicom-gw

# Set ownership
sudo chown -R dicom-gw:dicom-gw /opt/dicom-gw
sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
sudo chown -R dicom-gw:dicom-gw /var/log/dicom-gw
sudo chown -R dicom-gw:dicom-gw /etc/dicom-gw
```

### 3. Create Environment Files (Optional)

Create environment files for service-specific configuration:

```bash
# API service environment
sudo tee /etc/dicom-gw/dicom-gw-api.env <<EOF
DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
DICOM_GW_APP_ENV=production
DICOM_GW_APP_DEBUG=false
EOF

# Workers environment
sudo tee /etc/dicom-gw/dicom-gw-workers.env <<EOF
DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
DICOM_GW_APP_ENV=production
EOF

# SCP service environment
sudo tee /etc/dicom-gw/dicom-gw-scp.env <<EOF
DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
DICOM_GW_DICOM_AE_TITLE=DICOMGW
DICOM_GW_DICOM_PORT=104
EOF

# Set permissions
sudo chmod 640 /etc/dicom-gw/*.env
sudo chown dicom-gw:dicom-gw /etc/dicom-gw/*.env
```

### 4. Enable and Start Services

```bash
# Enable all services to start on boot
sudo systemctl enable dicom-gw.target

# Start all services
sudo systemctl start dicom-gw.target

# Or start individual services
sudo systemctl enable dicom-gw-api.service
sudo systemctl start dicom-gw-api.service
```

## Service Management

### Start Services

```bash
# Start all services
sudo systemctl start dicom-gw.target

# Start individual service
sudo systemctl start dicom-gw-api.service
sudo systemctl start dicom-gw-queue-worker.service
sudo systemctl start dicom-gw-forwarder-worker.service
sudo systemctl start dicom-gw-dbpool-worker.service
sudo systemctl start dicom-gw-scp.service
```

### Stop Services

```bash
# Stop all services
sudo systemctl stop dicom-gw.target

# Stop individual service
sudo systemctl stop dicom-gw-api.service
```

### Restart Services

```bash
# Restart all services
sudo systemctl restart dicom-gw.target

# Restart individual service
sudo systemctl restart dicom-gw-api.service
```

### Check Status

```bash
# Check all services status
sudo systemctl status dicom-gw.target

# Check individual service status
sudo systemctl status dicom-gw-api.service
sudo systemctl status dicom-gw-queue-worker.service
sudo systemctl status dicom-gw-forwarder-worker.service
sudo systemctl status dicom-gw-dbpool-worker.service
sudo systemctl status dicom-gw-scp.service

# Check if services are running
sudo systemctl is-active dicom-gw-api.service
```

### View Logs

```bash
# View logs for a service
sudo journalctl -u dicom-gw-api.service -f

# View logs for all services
sudo journalctl -u dicom-gw.target -f

# View recent logs
sudo journalctl -u dicom-gw-api.service -n 100

# View logs since boot
sudo journalctl -u dicom-gw-api.service -b

# View logs with timestamps
sudo journalctl -u dicom-gw-api.service --since "1 hour ago"
```

## Service Configuration

### API Service

The API service runs the FastAPI application with uvicorn.

**Key settings:**
- **Type**: `notify` - Supports systemd notification
- **Workers**: 4 (adjust based on CPU cores)
- **Port**: 8000 (localhost only, Nginx proxies to it)
- **Host**: 127.0.0.1 (not exposed directly)

**To modify workers:**
```bash
sudo systemctl edit dicom-gw-api.service
```

Add:
```ini
[Service]
ExecStart=
ExecStart=/opt/dicom-gw/venv/bin/uvicorn dicom_gw.api.main:app --host 127.0.0.1 --port 8000 --workers 8 --log-level info
```

### Worker Services

All worker services use the same base configuration with different entry points.

**Key settings:**
- **Type**: `simple` - Long-running processes
- **Restart**: `on-failure` - Restart on failure
- **RestartSec**: 10 seconds

### SCP Service

The SCP service runs the DICOM C-STORE receiver.

**Key settings:**
- **Port**: 104 (default DICOM port)
- **Network access**: Required for DICOM connections
- **Privileges**: Network I/O allowed

## Security Features

All services include comprehensive security hardening:

- **NoNewPrivileges**: Prevents privilege escalation
- **PrivateTmp**: Private /tmp directory
- **ProtectSystem**: Read-only /usr, /boot, /etc
- **ProtectHome**: Read-only home directories
- **ReadWritePaths**: Only specified paths writable
- **MemoryDenyWriteExecute**: Prevents code injection
- **RestrictAddressFamilies**: Limits network access
- **SystemCallFilter**: Restricts system calls

## Resource Limits

All services have resource limits configured:

- **LimitNOFILE**: 65536 (max open files)
- **LimitNPROC**: 4096 (max processes)

## Restart Policy

- **Restart**: `on-failure` - Restart on failure
- **RestartSec**: 10 seconds
- **StartLimitInterval**: 300 seconds
- **StartLimitBurst**: 5 attempts

If a service fails 5 times within 5 minutes, systemd will stop trying to restart it.

## Troubleshooting

### Service Won't Start

1. **Check service status**:
   ```bash
   sudo systemctl status dicom-gw-api.service
   ```

2. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gw-api.service -n 50
   ```

3. **Check permissions**:
   ```bash
   ls -la /opt/dicom-gw
   ls -la /var/lib/dicom-gw
   ```

4. **Check environment variables**:
   ```bash
   sudo systemctl show dicom-gw-api.service | grep Environment
   ```

5. **Check dependencies**:
   ```bash
   sudo systemctl status postgresql.service
   ```

### Service Keeps Restarting

1. **Check logs for errors**:
   ```bash
   sudo journalctl -u dicom-gw-api.service -f
   ```

2. **Check resource limits**:
   ```bash
   systemctl status dicom-gw-api.service | grep -i limit
   ```

3. **Check if port is in use**:
   ```bash
   sudo netstat -tlnp | grep :8000
   ```

### Permission Denied Errors

1. **Check file ownership**:
   ```bash
   sudo chown -R dicom-gw:dicom-gw /opt/dicom-gw
   sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
   ```

2. **Check directory permissions**:
   ```bash
   sudo chmod 750 /opt/dicom-gw
   sudo chmod 750 /var/lib/dicom-gw
   ```

### Database Connection Errors

1. **Verify database is running**:
   ```bash
   sudo systemctl status postgresql.service
   ```

2. **Check database URL in environment**:
   ```bash
   cat /etc/dicom-gw/dicom-gw-api.env
   ```

3. **Test database connection**:
   ```bash
   sudo -u dicom-gw psql -h localhost -U dicom_gw -d dicom_gw
   ```

## Customization

### Adjust Worker Count

Edit the service file:
```bash
sudo systemctl edit dicom-gw-api.service
```

### Change Port

Edit the service file and update the `--port` parameter:
```bash
sudo systemctl edit dicom-gw-api.service
```

### Add Environment Variables

Edit the environment file:
```bash
sudo nano /etc/dicom-gw/dicom-gw-api.env
```

Then reload the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart dicom-gw-api.service
```

## Monitoring

### Service Health Checks

```bash
# Check if all services are running
for service in dicom-gw-api dicom-gw-queue-worker dicom-gw-forwarder-worker dicom-gw-dbpool-worker dicom-gw-scp; do
    if systemctl is-active --quiet $service; then
        echo "$service: running"
    else
        echo "$service: stopped"
    fi
done
```

### Service Metrics

Monitor service resource usage:
```bash
# CPU and memory usage
systemctl status dicom-gw-api.service | grep -i memory
systemctl status dicom-gw-api.service | grep -i cpu

# Detailed resource usage
systemd-cgtop
```

## References

- [systemd.service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd Security Features](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#Security)

