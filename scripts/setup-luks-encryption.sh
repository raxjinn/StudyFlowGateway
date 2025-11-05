#!/bin/bash
# Setup script for LUKS encryption of DICOM Gateway storage

set -e

# Configuration
STORAGE_DEVICE="${1:-/dev/sdb1}"
MOUNT_POINT="/var/lib/dicom-gw/storage"
VOLUME_NAME="dicom-storage"
KEY_FILE="/etc/dicom-gw/luks-key"
SERVICE_USER="dicom-gw"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Check if device exists
if [ ! -b "$STORAGE_DEVICE" ]; then
    log_error "Device $STORAGE_DEVICE does not exist"
    exit 1
fi

log_info "Setting up LUKS encryption for $STORAGE_DEVICE"

# Check if already encrypted
if cryptsetup isLuks "$STORAGE_DEVICE" 2>/dev/null; then
    log_warn "Device $STORAGE_DEVICE is already encrypted with LUKS"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create key file directory
mkdir -p "$(dirname "$KEY_FILE")"

# Generate encryption key
log_info "Generating encryption key..."
dd if=/dev/urandom of="$KEY_FILE" bs=1024 count=4 2>/dev/null
chmod 400 "$KEY_FILE"

# Format device with LUKS
log_warn "WARNING: This will destroy all data on $STORAGE_DEVICE"
read -p "Are you sure you want to continue? (yes/NO) " -r
if [[ ! $REPLY == "yes" ]]; then
    log_info "Aborted"
    rm -f "$KEY_FILE"
    exit 1
fi

log_info "Formatting $STORAGE_DEVICE with LUKS..."
cryptsetup luksFormat "$STORAGE_DEVICE" "$KEY_FILE" --batch-mode

# Add key to LUKS
log_info "Adding key to LUKS..."
cryptsetup luksAddKey "$STORAGE_DEVICE" "$KEY_FILE"

# Open encrypted device
log_info "Opening encrypted device..."
cryptsetup luksOpen "$STORAGE_DEVICE" "$VOLUME_NAME" --key-file "$KEY_FILE"

# Create filesystem
log_info "Creating filesystem..."
if command -v mkfs.xfs &> /dev/null; then
    mkfs.xfs "/dev/mapper/$VOLUME_NAME"
    FSTYPE="xfs"
else
    mkfs.ext4 "/dev/mapper/$VOLUME_NAME"
    FSTYPE="ext4"
fi

# Create mount point
mkdir -p "$MOUNT_POINT"

# Mount device
log_info "Mounting encrypted device..."
mount "/dev/mapper/$VOLUME_NAME" "$MOUNT_POINT"

# Set permissions
log_info "Setting permissions..."
if id "$SERVICE_USER" &>/dev/null; then
    chown -R "$SERVICE_USER:$SERVICE_USER" "$MOUNT_POINT"
else
    log_warn "User $SERVICE_USER does not exist. Setting ownership to root."
    chown -R root:root "$MOUNT_POINT"
fi
chmod 750 "$MOUNT_POINT"

# Configure automatic mounting
log_info "Configuring automatic mounting..."

# Add to crypttab
if ! grep -q "^$VOLUME_NAME" /etc/crypttab; then
    echo "$VOLUME_NAME $STORAGE_DEVICE $KEY_FILE luks" >> /etc/crypttab
    log_info "Added entry to /etc/crypttab"
else
    log_warn "Entry already exists in /etc/crypttab"
fi

# Add to fstab
if ! grep -q "/dev/mapper/$VOLUME_NAME" /etc/fstab; then
    echo "/dev/mapper/$VOLUME_NAME $MOUNT_POINT $FSTYPE defaults 0 2" >> /etc/fstab
    log_info "Added entry to /etc/fstab"
else
    log_warn "Entry already exists in /etc/fstab"
fi

# Test automatic mounting
log_info "Testing automatic mounting..."
umount "$MOUNT_POINT"
cryptsetup luksClose "$VOLUME_NAME"

# Start systemd service
systemctl start "systemd-cryptsetup@$VOLUME_NAME.service"
sleep 2
mount -a

if mountpoint -q "$MOUNT_POINT"; then
    log_info "LUKS encryption setup completed successfully!"
    log_info "Encrypted device: $STORAGE_DEVICE"
    log_info "Mount point: $MOUNT_POINT"
    log_info "Key file: $KEY_FILE"
    log_warn "IMPORTANT: Backup the key file securely!"
    log_warn "Backup LUKS header: cryptsetup luksHeaderBackup $STORAGE_DEVICE --header-backup-file <backup-location>"
else
    log_error "Failed to mount encrypted device automatically"
    exit 1
fi

