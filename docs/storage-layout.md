# Storage Layout Documentation

This document describes the storage layout for the DICOM Gateway.

## Directory Structure

The DICOM Gateway uses the following directory structure:

```
/var/lib/dicom-gw/
├── storage/          - Main DICOM file storage
│   └── studies/      - Study directories (organized by Study Instance UID)
│       └── {study_instance_uid}/
│           └── {series_instance_uid}/
│               └── {sop_instance_uid}.dcm
├── incoming/         - Temporary incoming files (optional staging area)
├── queue/            - Queue processing area (optional)
├── forwarded/        - Successfully forwarded studies (optional archive)
├── failed/           - Failed forward attempts (optional archive)
└── tmp/              - Temporary files

/var/log/dicom-gw/    - Application logs

/etc/dicom-gw/        - Configuration files
└── tls/              - TLS certificates
```

## Permissions

All directories follow a strict permission model:

- **Base directories**: 750 (owner:rwx, group:r-x, others:---)
- **Owner**: `dicom-gw`
- **Group**: `dicom-gw`
- **Files**: 640 (owner:rw-, group:r--, others:---)

## Setup

### Automatic Setup (RPM Installation)

The RPM package automatically creates the directory structure during installation.

### Manual Setup

Use the setup script:

```bash
sudo scripts/setup-storage-layout.sh
```

This script:
1. Creates the service user (`dicom-gw`)
2. Creates all required directories
3. Sets correct ownership and permissions
4. Creates documentation file

### Verification

Verify the storage layout:

```bash
sudo scripts/verify-storage-layout.sh
```

This script checks:
- Directory existence
- Permissions
- Ownership
- Disk space
- SELinux context (if enabled)

## Storage Organization

### Study Storage

DICOM files are stored in a hierarchical structure based on identifiers:

```
storage/studies/
  └── {study_instance_uid}/
      └── {series_instance_uid}/
          └── {sop_instance_uid}.dcm
```

Example:
```
storage/studies/
  └── 1.2.840.113619.2.55.3.1234567890.1234567890/
      └── 1.2.840.113619.2.55.3.1234567890.1234567890.1/
          └── 1.2.840.113619.2.55.3.1234567890.1234567890.1.1.dcm
```

This structure:
- Organizes files by study
- Makes it easy to locate all files for a study
- Supports efficient backup and archival
- Maintains DICOM hierarchy

### Temporary Directories

- **incoming/**: Files being received (before processing)
- **queue/**: Files queued for processing
- **tmp/**: Temporary files during processing

These directories are cleaned automatically by the cleanup script.

### Archive Directories

- **forwarded/**: Successfully forwarded studies (optional)
- **failed/**: Failed forwarding attempts (optional)

These directories can be used for archival and auditing purposes.

## Disk Space Management

### Monitoring

Monitor disk space regularly:

```bash
# Check disk usage
df -h /var/lib/dicom-gw

# Check directory sizes
du -sh /var/lib/dicom-gw/*

# Find largest studies
find /var/lib/dicom-gw/storage -type d -exec du -sh {} \; | sort -h | tail -10
```

### Cleanup

Use the cleanup script to remove old temporary files:

```bash
sudo scripts/cleanup-storage.sh
```

Default retention:
- Temporary files: 7 days
- Failed forwarding: 90 days
- Forwarded studies: 365 days (optional)

### Quotas

Consider implementing disk quotas:

```bash
# Set quota for dicom-gw user
sudo setquota -u dicom-gw 100G 110G 0 0 /var/lib/dicom-gw

# Check quota
sudo quota -u dicom-gw
```

### Alerts

Set up alerts for low disk space:

```bash
# Example: Alert if usage > 90%
USAGE=$(df /var/lib/dicom-gw | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$USAGE" -gt 90 ]; then
    echo "WARNING: Disk usage is ${USAGE}%"
    # Send alert (email, monitoring system, etc.)
fi
```

## Backup Strategy

### What to Backup

1. **Configuration** (`/etc/dicom-gw/`):
   - Configuration files
   - TLS certificates (if using manual upload)
   - Environment files

2. **Database** (PostgreSQL):
   - All database tables
   - Metadata, jobs, audit logs
   - User accounts

3. **Storage** (`/var/lib/dicom-gw/storage/`):
   - DICOM files (if required by policy)
   - Consider archival instead of backup for large datasets

### What NOT to Backup

- Temporary directories (`tmp/`, `queue/`, `incoming/`)
- Log files (unless required for compliance)
- Failed forwarding attempts (unless required)

### Backup Example

```bash
# Backup configuration
tar -czf /backup/dicom-gw-config-$(date +%Y%m%d).tar.gz /etc/dicom-gw/

# Backup database
pg_dump -U dicom_gw dicom_gw | gzip > /backup/dicom-gw-db-$(date +%Y%m%d).sql.gz

# Backup storage (if needed)
# Note: This can be very large
tar -czf /backup/dicom-gw-storage-$(date +%Y%m%d).tar.gz /var/lib/dicom-gw/storage/
```

## Archival Strategy

For long-term storage, consider:

1. **Move to archive storage**: Copy studies to archive system after forwarding
2. **Compress old studies**: Compress studies older than X days
3. **Offline storage**: Move to tape or cold storage
4. **Delete after archival**: Remove from active storage after archival

## Security Considerations

1. **File Permissions**: Ensure strict permissions (750 for directories, 640 for files)
2. **SELinux**: Configure SELinux contexts if enabled
3. **Access Control**: Restrict access to storage directories
4. **Encryption**: Use LUKS encryption for storage volumes (see encryption-at-rest.md)
5. **Audit**: Log all file access (if required by compliance)

## SELinux Configuration

If SELinux is enabled, set appropriate contexts:

```bash
# Set SELinux context for storage
sudo semanage fcontext -a -t dicom_gw_storage_t "/var/lib/dicom-gw(/.*)?"
sudo restorecon -Rv /var/lib/dicom-gw

# Set SELinux context for logs
sudo semanage fcontext -a -t dicom_gw_log_t "/var/log/dicom-gw(/.*)?"
sudo restorecon -Rv /var/log/dicom-gw
```

## Maintenance

### Regular Tasks

1. **Daily**: Monitor disk space
2. **Weekly**: Run cleanup script
3. **Monthly**: Review and archive old studies
4. **Quarterly**: Verify backup integrity

### Troubleshooting

**Permission Denied Errors**:
```bash
# Check ownership
ls -la /var/lib/dicom-gw

# Fix ownership
sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
```

**Disk Full**:
```bash
# Find largest directories
du -sh /var/lib/dicom-gw/* | sort -h

# Clean up temporary files
sudo scripts/cleanup-storage.sh

# Consider archiving old studies
```

**SELinux Issues**:
```bash
# Check SELinux context
ls -Z /var/lib/dicom-gw

# Set correct context
sudo restorecon -Rv /var/lib/dicom-gw
```

## References

- [DICOM Standard Part 10: Media Storage](https://www.dicomstandard.org/current/)
- [Linux File Permissions](https://www.linux.com/training-tutorials/understanding-linux-file-permissions/)
- [SELinux Documentation](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/using_selinux/index)

