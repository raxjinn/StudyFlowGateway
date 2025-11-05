# Setup Scripts

This directory contains setup and utility scripts for the DICOM Gateway.

## Scripts

### `setup-luks-encryption.sh`
Automated script to set up LUKS encryption for DICOM storage volumes.

**Usage:**
```bash
sudo ./setup-luks-encryption.sh [device]
```

**Example:**
```bash
sudo ./setup-luks-encryption.sh /dev/sdb1
```

**Note:** This script must be run as root on a Linux system.

### `generate-encryption-key.sh`
Generates an encryption key for database encryption (pgcrypto).

**Usage:**
```bash
sudo ./generate-encryption-key.sh [key-file-path]
```

**Example:**
```bash
sudo ./generate-encryption-key.sh /etc/dicom-gw/db-encryption.key
```

**Note:** This script must be run as root on a Linux system.

### `setup-storage-layout.sh`
Creates the complete storage directory structure with correct permissions.

**Usage:**
```bash
sudo ./setup-storage-layout.sh
```

**Note:** This script must be run as root on a Linux system.

### `verify-storage-layout.sh`
Verifies that the storage layout is correctly configured.

**Usage:**
```bash
sudo ./verify-storage-layout.sh
```

**Note:** This script can be run as root or the dicom-gw user.

### `cleanup-storage.sh`
Cleans up temporary files and old data from storage directories.

**Usage:**
```bash
sudo ./cleanup-storage.sh
```

**Note:** This script can be run as root or the dicom-gw user. Configure retention periods in the script.

## Platform Notes

These scripts are designed for Linux systems (RHEL/Alma/Rocky 8+ or Ubuntu/Debian).

**On Windows (development):**
- These scripts cannot be executed on Windows
- They are meant for deployment on Linux servers
- File permissions will be set correctly during RPM package installation
- Or manually when copied to a Linux system: `chmod +x script-name.sh`

**On Linux (production):**
- Make scripts executable: `chmod +x script-name.sh`
- Run with appropriate permissions (usually root)
- Scripts will be automatically made executable during RPM installation

## Security Notes

- Always review scripts before running them
- Ensure you have backups before running destructive operations
- Store encryption keys securely
- Follow the main documentation in `docs/encryption-at-rest.md`

