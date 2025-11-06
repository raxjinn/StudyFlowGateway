# Scaling Guide

The DICOM Gateway is designed for horizontal scaling to handle large volumes of studies. This guide explains how to scale the system to meet your throughput requirements.

## Architecture Overview

The gateway uses a **PostgreSQL-backed job queue** with **SKIP LOCKED** pattern, which allows multiple worker instances to process jobs concurrently without conflicts. This enables true horizontal scaling.

### Scalability Features

1. **SKIP LOCKED**: PostgreSQL's `SELECT FOR UPDATE SKIP LOCKED` ensures multiple workers never process the same job
2. **Unique Worker IDs**: Each worker instance has a unique identifier for tracking
3. **LISTEN/NOTIFY**: Real-time PostgreSQL notifications wake workers when jobs arrive
4. **Batch Processing**: Workers process multiple jobs in batches for efficiency
5. **Stateless Workers**: Workers don't share state, allowing easy scaling

## Worker Types

### Queue Worker
- Processes received DICOM files (metadata extraction)
- Creates forwarding jobs
- **Default**: 1 instance
- **Scales to**: 10+ instances (limited by database connections)

### Forwarder Worker
- Forwards studies to remote PACS systems
- Handles retries and failures
- **Default**: 1 instance
- **Scales to**: 20+ instances (network I/O bound)

### DB Pool Worker
- Batches database writes for performance
- Processes metrics and audit logs
- **Default**: 1 instance
- **Scales to**: 3-5 instances (database write bound)

## Scaling Methods

### Method 1: Using Template Services (Recommended)

The gateway includes systemd template unit files (`@.service`) that allow easy horizontal scaling:

```bash
# Scale queue workers to 3 instances
sudo systemctl enable dicom-gw-queue-worker@0
sudo systemctl enable dicom-gw-queue-worker@1
sudo systemctl enable dicom-gw-queue-worker@2
sudo systemctl start dicom-gw-queue-worker@{0..2}

# Scale forwarder workers to 5 instances
sudo systemctl enable dicom-gw-forwarder-worker@{0..4}
sudo systemctl start dicom-gw-forwarder-worker@{0..4}
```

### Method 2: Using Scaling Script

A helper script automates worker scaling:

```bash
# Show current worker status
sudo ./scripts/scale-workers.sh all

# Scale queue workers to 3 instances
sudo ./scripts/scale-workers.sh queue 3

# Scale forwarder workers to 5 instances
sudo ./scripts/scale-workers.sh forwarder 5

# Scale dbpool workers to 2 instances
sudo ./scripts/scale-workers.sh dbpool 2

# Scale down queue workers to 1 instance
sudo ./scripts/scale-workers.sh queue 1
```

### Method 3: Manual Scaling

You can manually manage individual worker instances:

```bash
# Start a specific worker instance
sudo systemctl start dicom-gw-queue-worker@0
sudo systemctl start dicom-gw-forwarder-worker@1

# Stop a specific worker instance
sudo systemctl stop dicom-gw-queue-worker@0

# Check status
sudo systemctl status dicom-gw-queue-worker@0

# View logs
sudo journalctl -u dicom-gw-queue-worker@0 -f
```

## Scaling Recommendations

### Small Deployment (< 100 studies/hour)
- **Queue Workers**: 1
- **Forwarder Workers**: 1-2
- **DB Pool Workers**: 1
- **Database Pool**: min=4, max=16

### Medium Deployment (100-1000 studies/hour)
- **Queue Workers**: 2-3
- **Forwarder Workers**: 3-5
- **DB Pool Workers**: 1-2
- **Database Pool**: min=8, max=32

### Large Deployment (1000-10000 studies/hour)
- **Queue Workers**: 5-10
- **Forwarder Workers**: 10-20
- **DB Pool Workers**: 2-3
- **Database Pool**: min=16, max=64

### Very Large Deployment (> 10000 studies/hour)
- **Queue Workers**: 10-20
- **Forwarder Workers**: 20-50
- **DB Pool Workers**: 3-5
- **Database Pool**: min=32, max=100
- Consider distributed deployment across multiple servers

## Configuration for High Throughput

### Database Connection Pool

Update `/etc/dicom-gw/config.yaml`:

```yaml
database:
  pool_min: 16
  pool_max: 64
  pool_acquire_timeout: 30
```

Or use environment variables:

```bash
export DATABASE_POOL_MIN=16
export DATABASE_POOL_MAX=64
```

### Worker Configuration

```yaml
workers:
  queue_worker:
    batch_size: 100        # Process 100 jobs per batch
    poll_interval: 1.0     # Poll every second
  
  forwarder_worker:
    batch_size: 10         # Process 10 forward jobs per batch
    poll_interval: 0.5     # Poll every 0.5 seconds
  
  dbpool_worker:
    batch_size: 5000       # Batch 5000 database writes
    flush_interval: 2.0    # Flush every 2 seconds
```

## Monitoring Scaling

### Check Worker Status

```bash
# List all running worker instances
systemctl list-units 'dicom-gw-*-worker@*' --state=running

# Count workers by type
systemctl list-units 'dicom-gw-queue-worker@*' --state=running | wc -l
systemctl list-units 'dicom-gw-forwarder-worker@*' --state=running | wc -l
```

### View Metrics

Access the metrics endpoint:

```bash
curl http://localhost:8000/api/v1/metrics/queue
curl http://localhost:8000/api/v1/metrics/workers
```

### Prometheus Metrics

The gateway exposes Prometheus metrics at `/metrics/prometheus`:

- `dicom_gw_queue_depth{job_type}` - Number of pending jobs
- `dicom_gw_processing_jobs{job_type}` - Number of jobs being processed
- `dicom_gw_worker_uptime{worker_type,worker_id}` - Worker uptime
- `dicom_gw_queue_jobs_total{job_type,status}` - Job processing statistics

## Performance Considerations

### Database Bottlenecks

- **Connection Pool**: Each worker uses database connections. Monitor pool usage
- **Write Performance**: DB Pool Worker batches writes to reduce database load
- **Indexes**: Ensure proper indexes on `jobs` and `forward_jobs` tables

### Network Bottlenecks

- **Forwarder Workers**: Network I/O bound when forwarding to remote PACS
- **Concurrent Connections**: Each forwarder worker can handle multiple destinations
- **Bandwidth**: Ensure sufficient network bandwidth for DICOM transfers

### CPU/Memory

- **Queue Workers**: CPU bound during metadata extraction (pydicom parsing)
- **Memory**: Each worker uses ~100-200MB RAM
- **File I/O**: Disk performance critical for DICOM file storage

## Scaling Strategies

### Vertical Scaling (Single Server)

1. **Increase Database Pool Size**: Allows more concurrent connections
2. **Increase Worker Batch Sizes**: Process more jobs per batch
3. **Reduce Poll Intervals**: Workers check for jobs more frequently
4. **Add More CPU/RAM**: Support more worker instances

### Horizontal Scaling (Multiple Servers)

1. **Shared Storage**: Use NFS or GlusterFS for DICOM files
2. **PostgreSQL Cluster**: Use read replicas or connection pooling (PgBouncer)
3. **Load Balancing**: Multiple API instances behind Nginx
4. **Worker Distribution**: Run workers on different servers

## Troubleshooting

### Workers Not Processing Jobs

```bash
# Check if workers are running
systemctl status dicom-gw-queue-worker@0

# Check database connection
sudo -u dicom-gw /opt/dicom-gw/venv/bin/python scripts/test-db-connection.sh

# Check queue depth
curl http://localhost:8000/api/v1/metrics/queue
```

### Too Many Database Connections

```bash
# Check active connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='dicom_gw';"

# Reduce worker count or increase pool size
```

### Workers Crashing

```bash
# Check logs
sudo journalctl -u dicom-gw-queue-worker@0 -n 100

# Check system resources
top
free -h
df -h
```

## Best Practices

1. **Start Small**: Begin with default worker counts and scale up based on metrics
2. **Monitor Metrics**: Use Prometheus/Grafana to track queue depth and processing times
3. **Balance Workers**: Keep queue workers ahead of forwarder workers to prevent backlogs
4. **Database First**: Ensure database can handle the connection load before scaling workers
5. **Test Scaling**: Test scaling in a staging environment before production

## Example Scaling Workflow

```bash
# 1. Check current status
sudo ./scripts/scale-workers.sh all

# 2. Monitor queue depth
watch -n 1 'curl -s http://localhost:8000/api/v1/metrics/queue | jq'

# 3. If queue is building up, scale up workers
sudo ./scripts/scale-workers.sh queue 5
sudo ./scripts/scale-workers.sh forwarder 10

# 4. Monitor worker utilization
watch -n 1 'systemctl list-units "dicom-gw-*-worker@*" --state=running | wc -l'

# 5. Scale down when load decreases
sudo ./scripts/scale-workers.sh queue 2
sudo ./scripts/scale-workers.sh forwarder 3
```

## Next Steps

- Review [Performance Tuning](PERFORMANCE.md) for optimization tips
- Check [Monitoring](MONITORING.md) for metrics and alerts
- See [Operations Guide](OPERATIONS.md) for day-to-day management

