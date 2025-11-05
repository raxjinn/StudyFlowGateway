# Encryption at Rest for DICOM Gateway

This document describes the encryption at rest strategy for the DICOM Gateway, including disk-level encryption (LUKS) and database-level encryption (pgcrypto).

## Overview

The DICOM Gateway supports encryption at rest at two levels:

1. **Disk-Level Encryption (LUKS)** - Encrypts the entire storage volume where DICOM files are stored
2. **Database-Level Encryption (pgcrypto)** - Encrypts sensitive fields in the PostgreSQL database

## Disk-Level Encryption with LUKS

### Prerequisites

- Root access to the server
- Available disk or partition for encrypted storage
- LUKS utilities installed (`cryptsetup`)

### Setting Up LUKS Encryption

#### 1. Install Required Packages

```bash
# RHEL/Alma/Rocky Linux 8+
sudo dnf install cryptsetup

# Ubuntu/Debian
sudo apt-get install cryptsetup
```

#### 2. Create Encrypted Volume

**Option A: Encrypt Existing Partition**

```bash
# WARNING: This will destroy all data on the partition
# Replace /dev/sdb1 with your target partition
sudo cryptsetup luksFormat /dev/sdb1

# Enter passphrase when prompted
# Use a strong passphrase and store it securely
```

**Option B: Create Encrypted Loop Device (for testing)**

```bash
# Create a 10GB file
sudo dd if=/dev/zero of=/var/lib/dicom-gw/encrypted-storage.img bs=1M count=10240

# Set up loop device
sudo losetup /dev/loop0 /var/lib/dicom-gw/encrypted-storage.img

# Format with LUKS
sudo cryptsetup luksFormat /dev/loop0
```

#### 3. Open the Encrypted Volume

```bash
# Open the encrypted device
sudo cryptsetup luksOpen /dev/sdb1 dicom-storage

# Or for loop device
sudo cryptsetup luksOpen /dev/loop0 dicom-storage
```

This creates a mapped device at `/dev/mapper/dicom-storage`.

#### 4. Create Filesystem

```bash
# Format with ext4 (or xfs for RHEL)
sudo mkfs.ext4 /dev/mapper/dicom-storage

# Or for xfs
sudo mkfs.xfs /dev/mapper/dicom-storage
```

#### 5. Mount the Encrypted Volume

```bash
# Create mount point
sudo mkdir -p /var/lib/dicom-gw/storage

# Mount the encrypted volume
sudo mount /dev/mapper/dicom-storage /var/lib/dicom-gw/storage

# Set proper permissions
sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw/storage
sudo chmod 750 /var/lib/dicom-gw/storage
```

#### 6. Configure Automatic Mounting

Create a key file for automatic mounting (optional but recommended for production):

```bash
# Generate random key
sudo dd if=/dev/urandom of=/etc/dicom-gw/luks-key bs=1024 count=4
sudo chmod 400 /etc/dicom-gw/luks-key

# Add key to LUKS slot
sudo cryptsetup luksAddKey /dev/sdb1 /etc/dicom-gw/luks-key

# Update /etc/crypttab
echo "dicom-storage /dev/sdb1 /etc/dicom-gw/luks-key luks" | sudo tee -a /etc/crypttab

# Update /etc/fstab
echo "/dev/mapper/dicom-storage /var/lib/dicom-gw/storage ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

#### 7. Test Automatic Mounting

```bash
# Unmount and close
sudo umount /var/lib/dicom-gw/storage
sudo cryptsetup luksClose dicom-storage

# Test automatic mounting
sudo systemctl start systemd-cryptsetup@dicom-storage.service
sudo mount -a
```

### Security Considerations

1. **Key Management**: Store LUKS keys securely (e.g., in a key management service or hardware security module)
2. **Backup Keys**: Keep secure backups of LUKS keys and passphrases
3. **Key Rotation**: Consider rotating keys periodically
4. **Access Control**: Restrict access to key files (chmod 400)
5. **Monitoring**: Monitor mount status and encryption health

### Troubleshooting

**Device not mounting on boot:**
- Check `/etc/crypttab` and `/etc/fstab` syntax
- Verify key file permissions and path
- Check systemd journal: `journalctl -u systemd-cryptsetup@dicom-storage`

**Performance:**
- LUKS encryption adds minimal overhead (~5-10%)
- Use AES-NI hardware acceleration (available on modern CPUs)
- Consider using faster ciphers (e.g., `aes-xts-plain64`)

## Database-Level Encryption with pgcrypto

### Prerequisites

- PostgreSQL 14+ with pgcrypto extension
- Database superuser access

### Setting Up pgcrypto

#### 1. Enable pgcrypto Extension

```sql
-- Connect to the database
psql -U postgres -d dicom_gw

-- Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

#### 2. Generate Encryption Key

Generate a strong encryption key (32 bytes for AES-256):

```bash
# Generate random key (base64 encoded)
openssl rand -base64 32

# Store securely (e.g., in /etc/dicom-gw/db-encryption.key)
echo "YOUR_ENCRYPTION_KEY" | sudo tee /etc/dicom-gw/db-encryption.key
sudo chmod 400 /etc/dicom-gw/db-encryption.key
sudo chown dicom-gw:dicom-gw /etc/dicom-gw/db-encryption.key
```

**Important**: Set the encryption key as an environment variable:

```bash
# In /etc/dicom-gw/dicom-gw-api.service or .env file
export DICOM_GW_DB_ENCRYPTION_KEY="your-encryption-key-here"
```

#### 3. Encrypting Sensitive Fields

The DICOM Gateway automatically encrypts sensitive fields using pgcrypto. The following fields are encrypted:

- User passwords (already hashed with argon2id, additional encryption optional)
- TLS certificate private keys
- Database connection passwords (if stored in config)
- Audit log metadata (if containing sensitive information)

### Using pgcrypto in Application

The application uses pgcrypto functions for encryption:

```sql
-- Encrypt a value
SELECT pgp_sym_encrypt('sensitive_data', 'encryption_key');

-- Decrypt a value
SELECT pgp_sym_decrypt(encrypted_value, 'encryption_key');
```

### Key Rotation

To rotate encryption keys:

1. **Backup the database**:
```bash
pg_dump -U dicom_gw dicom_gw > backup.sql
```

2. **Decrypt with old key and re-encrypt with new key**:
```sql
-- Example: Rotate encryption for a field
UPDATE table_name
SET encrypted_field = pgp_sym_encrypt(
    pgp_sym_decrypt(encrypted_field, 'old_key'),
    'new_key'
);
```

3. **Update application configuration** with new key
4. **Test thoroughly** before removing old key

### Security Best Practices

1. **Key Storage**: Store encryption keys separately from encrypted data
2. **Key Rotation**: Rotate keys periodically (e.g., annually)
3. **Backup Keys**: Keep secure backups of encryption keys
4. **Access Control**: Restrict access to key files and environment variables
5. **Key Management Service**: Consider using a key management service (e.g., HashiCorp Vault, AWS KMS)

## Compliance and HIPAA

Both encryption methods support HIPAA compliance:

- **LUKS**: Meets encryption requirements for PHI stored on disk
- **pgcrypto**: Meets encryption requirements for PHI stored in database

Ensure that:
- Encryption keys are stored securely
- Access to keys is logged and audited
- Key rotation procedures are documented
- Encryption status is monitored

## Monitoring Encryption Status

### Check LUKS Status

```bash
# List encrypted devices
sudo cryptsetup status dicom-storage

# Check mount status
mount | grep dicom-storage

# Monitor encryption performance
iostat -x 1
```

### Check Database Encryption

```sql
-- Verify pgcrypto is enabled
SELECT * FROM pg_extension WHERE extname = 'pgcrypto';

-- Check encrypted fields (if using application-level encryption)
-- Query your encrypted tables to verify data is encrypted
```

## Disaster Recovery

### LUKS Recovery

1. **Backup LUKS header**:
```bash
sudo cryptsetup luksHeaderBackup /dev/sdb1 --header-backup-file /secure/location/luks-header.backup
```

2. **Restore LUKS header** (if corrupted):
```bash
sudo cryptsetup luksHeaderRestore /dev/sdb1 --header-backup-file /secure/location/luks-header.backup
```

3. **Recovery passphrase**: Store recovery passphrase securely

### Database Encryption Recovery

1. **Backup encryption keys** separately from database
2. **Test key restoration** in non-production environment
3. **Document recovery procedures** in runbook

## References

- [LUKS Documentation](https://gitlab.com/cryptsetup/cryptsetup/-/blob/main/docs/README.md)
- [PostgreSQL pgcrypto Documentation](https://www.postgresql.org/docs/current/pgcrypto.html)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)

