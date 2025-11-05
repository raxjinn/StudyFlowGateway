# Operations Runbook

This guide covers common operational tasks for the DICOM Gateway.

## Service Management

### Start/Stop Services

```bash
# Start all services
sudo systemctl start dicom-gateway.target

# Stop all services
sudo systemctl stop dicom-gateway.target

# Restart all services
sudo systemctl restart dicom-gateway.target

# Reload configuration (if supported)
sudo systemctl reload dicom-gateway.target

# Check status
sudo systemctl status dicom-gateway.target
```

### Individual Services

```bash
# API service
sudo systemctl start dicom-gw-api.service
sudo systemctl stop dicom-gw-api.service
sudo systemctl restart dicom-gw-api.service

# SCP receiver
sudo systemctl start dicom-gw-scp.service
sudo systemctl restart dicom-gw-scp.service

# Queue worker
sudo systemctl start dicom-gw-queue-worker.service
sudo systemctl restart dicom-gw-queue-worker.service

# Forwarder worker
sudo systemctl start dicom-gw-forwarder-worker.service
sudo systemctl restart dicom-gw-forwarder-worker.service

# DB pool worker
sudo systemctl start dicom-gw-dbpool-worker.service
sudo systemctl restart dicom-gw-dbpool-worker.service
```

### Enable/Disable Services

```bash
# Enable services to start on boot
sudo systemctl enable dicom-gateway.target

# Disable services
sudo systemctl disable dicom-gateway.target
```

## Monitoring

### View Logs

```bash
# All services
sudo journalctl -u dicom-gateway.target -f

# Specific service
sudo journalctl -u dicom-gw-api.service -f

# Last 100 lines
sudo journalctl -u dicom-gw-api.service -n 100

# Since boot
sudo journalctl -u dicom-gw-api.service -b

# Since specific time
sudo journalctl -u dicom-gw-api.service --since "1 hour ago"
sudo journalctl -u dicom-gw-api.service --since "2024-01-01 00:00:00"

# Log files (if configured)
sudo tail -f /var/log/dicom-gw/api.log
sudo tail -f /var/log/dicom-gw/scp.log
```

### Health Checks

```bash
# API health
curl http://localhost:8000/api/v1/health

# Liveness probe
curl http://localhost:8000/api/v1/health/live

# Readiness probe
curl http://localhost:8000/api/v1/health/ready
```

### Metrics

```bash
# System metrics
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/metrics

# Prometheus metrics
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/metrics/prometheus

# Queue statistics
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/metrics/queue
```

## Common Operations

### Check System Status

```bash
# Service status
sudo systemctl status dicom-gateway.target

# Process status
ps aux | grep dicom

# Port usage
sudo netstat -tlnp | grep -E '(104|8000|443)'
# or
sudo ss -tlnp | grep -E '(104|8000|443)'

# Disk usage
df -h /var/lib/dicom-gw

# Database connections
sudo -u postgres psql -d dicom_gateway -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='dicom_gateway';"
```

### View Queue Status

```bash
# Via API
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/queues/stats

# Via database
sudo -u postgres psql -d dicom_gateway -c \
  "SELECT status, count(*) FROM forward_jobs GROUP BY status;"
```

### Retry Failed Jobs

```bash
# Retry all dead-letter jobs
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/queues/retry \
  -d '{}'

# Retry specific jobs
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/queues/retry \
  -d '{"job_ids": ["uuid1", "uuid2"]}'
```

### Replay Study

```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/queues/replay/1.2.3.4.5.6.7.8.9.10 \
  -d '{"destination_ids": ["destination-uuid"]}'
```

### Manage Destinations

```bash
# List destinations
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/destinations

# Enable/disable destination
curl -X PUT \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/destinations/{id} \
  -d '{"enabled": true}'
```

### View Studies

```bash
# List studies
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/studies?limit=10&skip=0"

# Get study details
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/studies/{study_id}

# Search by UID
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/studies/uid/1.2.3.4.5.6.7.8.9.10
```

## Maintenance Tasks

### Database Maintenance

```bash
# Vacuum database
sudo -u postgres psql -d dicom_gateway -c "VACUUM ANALYZE;"

# Check database size
sudo -u postgres psql -d dicom_gateway -c \
  "SELECT pg_size_pretty(pg_database_size('dicom_gateway'));"

# Check table sizes
sudo -u postgres psql -d dicom_gateway -c "
  SELECT schemaname, tablename, 
         pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Reindex
sudo -u postgres psql -d dicom_gateway -c "REINDEX DATABASE dicom_gateway;"
```

### Cleanup Old Data

```bash
# Cleanup old failed jobs (older than 30 days)
sudo -u postgres psql -d dicom_gateway -c "
  DELETE FROM forward_jobs
  WHERE status = 'failed'
    AND updated_at < NOW() - INTERVAL '30 days';
"

# Cleanup old audit logs (older than 1 year)
sudo -u postgres psql -d dicom_gateway -c "
  DELETE FROM audit_logs
  WHERE created_at < NOW() - INTERVAL '1 year';
"

# Archive old studies (move to archive)
# Manual process or scheduled script
```

### Storage Cleanup

```bash
# Cleanup temporary files
sudo -u dicom-gw /opt/dicom-gw/scripts/cleanup-storage.sh

# Check storage usage
du -sh /var/lib/dicom-gw/storage/*

# Find large files
find /var/lib/dicom-gw/storage -type f -size +100M -ls
```

### Log Rotation

```bash
# Check logrotate status
sudo logrotate -d /etc/logrotate.d/dicom-gw

# Force log rotation
sudo logrotate -f /etc/logrotate.d/dicom-gw

# View logrotate configuration
cat /etc/logrotate.d/dicom-gw
```

## Troubleshooting

### Service Won't Start

1. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gw-api.service -n 100
   ```

2. **Check configuration**:
   ```bash
   sudo -u dicom-gw python -c "from dicom_gw.config.settings import get_settings; print(get_settings())"
   ```

3. **Check permissions**:
   ```bash
   ls -la /var/lib/dicom-gw/
   ls -la /etc/dicom-gw/
   ```

4. **Check database**:
   ```bash
   sudo -u postgres psql -d dicom_gateway -c "SELECT 1;"
   ```

### High Queue Depth

1. **Check queue statistics**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/queues/stats
   ```

2. **Check worker status**:
   ```bash
   sudo systemctl status dicom-gw-queue-worker.service
   sudo systemctl status dicom-gw-forwarder-worker.service
   ```

3. **Check destination status**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/destinations
   ```

4. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gw-forwarder-worker.service -n 100
   ```

### Forwarding Failures

1. **Check destination connectivity**:
   ```bash
   # Test network connectivity
   telnet pacs.example.com 104
   
   # Test with storescu (dcmtk)
   storescu -aec GATEWAY_AE -aet REMOTE_AE pacs.example.com 104 test.dcm
   ```

2. **Check destination configuration**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/destinations/{id}
   ```

3. **Check failed jobs**:
   ```bash
   sudo -u postgres psql -d dicom_gateway -c "
     SELECT id, destination_id, error_message, attempts
     FROM forward_jobs
     WHERE status = 'failed'
     ORDER BY updated_at DESC
     LIMIT 10;
   "
   ```

### Performance Issues

1. **Check system resources**:
   ```bash
   # CPU usage
   top
   htop
   
   # Memory usage
   free -h
   
   # Disk I/O
   iostat -x 1
   
   # Network
   iftop
   ```

2. **Check database performance**:
   ```bash
   # Active queries
   sudo -u postgres psql -d dicom_gateway -c "
     SELECT pid, now() - pg_stat_activity.query_start AS duration, query
     FROM pg_stat_activity
     WHERE state = 'active'
     ORDER BY duration DESC;
   "
   
   # Connection pool
   sudo -u postgres psql -d dicom_gateway -c "
     SELECT count(*), state
     FROM pg_stat_activity
     WHERE datname = 'dicom_gateway'
     GROUP BY state;
   "
   ```

3. **Check metrics**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/metrics
   ```

## Backup and Recovery

### Database Backup

```bash
# Full backup
sudo -u postgres pg_dump dicom_gateway > backup_$(date +%Y%m%d).sql

# Compressed backup
sudo -u postgres pg_dump dicom_gateway | gzip > backup_$(date +%Y%m%d).sql.gz

# Custom format (recommended)
sudo -u postgres pg_dump -Fc dicom_gateway > backup_$(date +%Y%m%d).dump

# Restore
sudo -u postgres psql dicom_gateway < backup_20240101.sql
sudo -u postgres pg_restore -d dicom_gateway backup_20240101.dump
```

### Configuration Backup

```bash
# Backup configuration
sudo tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  /etc/dicom-gw/ \
  /var/lib/dicom-gw/storage/

# Restore
sudo tar -xzf config_backup_20240101.tar.gz -C /
```

## Upgrade Procedures

### Pre-Upgrade

1. **Backup database**:
   ```bash
   sudo -u postgres pg_dump -Fc dicom_gateway > pre_upgrade_backup.dump
   ```

2. **Backup configuration**:
   ```bash
   sudo cp -r /etc/dicom-gw /etc/dicom-gw.backup
   ```

3. **Stop services**:
   ```bash
   sudo systemctl stop dicom-gateway.target
   ```

### Upgrade

1. **Install new version**:
   ```bash
   sudo rpm -Uvh dicom-gateway-0.2.0-1.el8.x86_64.rpm
   ```

2. **Run database migrations**:
   ```bash
   cd /opt/dicom-gw
   source venv/bin/activate
   alembic upgrade head
   ```

3. **Update configuration** (if needed):
   ```bash
   # Compare old and new config
   diff /etc/dicom-gw.backup/config.yaml /etc/dicom-gw/config.yaml
   ```

### Post-Upgrade

1. **Start services**:
   ```bash
   sudo systemctl start dicom-gateway.target
   ```

2. **Verify functionality**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

3. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gateway.target -f
   ```

## Emergency Procedures

### Service Recovery

```bash
# If services are down, restart all
sudo systemctl restart dicom-gateway.target

# If database is down, check PostgreSQL
sudo systemctl status postgresql-14
sudo systemctl start postgresql-14
```

### Rollback

```bash
# Stop services
sudo systemctl stop dicom-gateway.target

# Restore database
sudo -u postgres pg_restore -d dicom_gateway pre_upgrade_backup.dump

# Restore configuration
sudo cp -r /etc/dicom-gw.backup/* /etc/dicom-gw/

# Downgrade package (if needed)
sudo rpm -Uvh --oldpackage dicom-gateway-0.1.0-1.el8.x86_64.rpm

# Start services
sudo systemctl start dicom-gateway.target
```

## Next Steps

- Review [Monitoring Guide](MONITORING.md)
- Setup [Backup and Recovery](BACKUP.md)
- Configure [Alerts](ALERTS.md)

