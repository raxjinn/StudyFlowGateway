#!/bin/bash
# Setup script for DICOM Gateway storage layout
# Creates directory structure with correct permissions

set -e

# Configuration
BASE_DATA_DIR="/var/lib/dicom-gw"
BASE_LOG_DIR="/var/log/dicom-gw"
BASE_CONFIG_DIR="/etc/dicom-gw"
SERVICE_USER="dicom-gw"
SERVICE_GROUP="dicom-gw"

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

log_info "Setting up DICOM Gateway storage layout"

# Create service user if it doesn't exist
if ! id -u "$SERVICE_USER" &>/dev/null; then
    log_info "Creating service user: $SERVICE_USER"
    useradd -r -s /bin/false -d "$BASE_DATA_DIR" -c "DICOM Gateway Service User" "$SERVICE_USER"
    log_info "Created service user: $SERVICE_USER"
else
    log_info "Service user already exists: $SERVICE_USER"
fi

# Create base directories
log_info "Creating base directories..."

# Data directories
mkdir -p "$BASE_DATA_DIR"/{storage,incoming,queue,forwarded,failed,tmp}
log_info "Created data directories under $BASE_DATA_DIR"

# Log directories
mkdir -p "$BASE_LOG_DIR"
log_info "Created log directory: $BASE_LOG_DIR"

# Config directories
mkdir -p "$BASE_CONFIG_DIR"/tls
log_info "Created config directory: $BASE_CONFIG_DIR"

# Set ownership
log_info "Setting ownership to $SERVICE_USER:$SERVICE_GROUP"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$BASE_LOG_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$BASE_CONFIG_DIR"

# Set permissions
log_info "Setting directory permissions..."

# Base directories: 750 (owner:rwx, group:r-x, others:---)
chmod 750 "$BASE_DATA_DIR"
chmod 750 "$BASE_LOG_DIR"
chmod 750 "$BASE_CONFIG_DIR"
chmod 750 "$BASE_CONFIG_DIR"/tls

# Storage subdirectories: 750
chmod 750 "$BASE_DATA_DIR"/storage
chmod 750 "$BASE_DATA_DIR"/incoming
chmod 750 "$BASE_DATA_DIR"/queue
chmod 750 "$BASE_DATA_DIR"/forwarded
chmod 750 "$BASE_DATA_DIR"/failed
chmod 750 "$BASE_DATA_DIR"/tmp

# Create storage subdirectory structure
log_info "Creating storage subdirectory structure..."

# Storage directory uses a hierarchical structure based on study UIDs
# This will be created automatically by the application, but we ensure parent exists
mkdir -p "$BASE_DATA_DIR"/storage/studies
chmod 750 "$BASE_DATA_DIR"/storage/studies
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/storage/studies

# Create .gitkeep files to preserve directory structure
touch "$BASE_DATA_DIR"/storage/.gitkeep
touch "$BASE_DATA_DIR"/incoming/.gitkeep
touch "$BASE_DATA_DIR"/queue/.gitkeep
touch "$BASE_DATA_DIR"/forwarded/.gitkeep
touch "$BASE_DATA_DIR"/failed/.gitkeep
touch "$BASE_DATA_DIR"/tmp/.gitkeep

chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/storage/.gitkeep
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/incoming/.gitkeep
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/queue/.gitkeep
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/forwarded/.gitkeep
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/failed/.gitkeep
chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/tmp/.gitkeep

# Create example directory structure documentation
log_info "Creating storage layout documentation..."
cat > "$BASE_DATA_DIR"/STORAGE_LAYOUT.txt <<EOF
DICOM Gateway Storage Layout
============================

This directory contains the storage layout for the DICOM Gateway.

Directory Structure:
$BASE_DATA_DIR/
├── storage/          - Main DICOM file storage (organized by Study Instance UID)
│   └── studies/      - Study directories (auto-created)
├── incoming/         - Temporary incoming files (optional, for staging)
├── queue/            - Queue processing area (optional)
├── forwarded/        - Successfully forwarded studies (optional archive)
├── failed/           - Failed forward attempts (optional archive)
└── tmp/              - Temporary files

Permissions:
- All directories: 750 (owner:rwx, group:r-x, others:---)
- Owner: $SERVICE_USER
- Group: $SERVICE_GROUP

Storage Organization:
The storage directory follows a hierarchical structure:
storage/
  └── studies/
      └── {study_instance_uid}/
          └── {series_instance_uid}/
              └── {sop_instance_uid}.dcm

This structure is created automatically by the application when studies are received.

Disk Space:
- Monitor disk space regularly
- Consider implementing disk quotas
- Set up alerts for low disk space
- Archive old studies if needed

Backup:
- Backup configuration: $BASE_CONFIG_DIR
- Backup database: PostgreSQL database
- Backup storage: Consider backing up $BASE_DATA_DIR/storage
- Do not backup temporary directories (tmp, queue, incoming)

EOF

chown "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DATA_DIR"/STORAGE_LAYOUT.txt
chmod 640 "$BASE_DATA_DIR"/STORAGE_LAYOUT.txt

# Display summary
log_info "Storage layout setup completed successfully!"
echo ""
echo "Directory Structure:"
echo "  Data:    $BASE_DATA_DIR"
echo "  Logs:    $BASE_LOG_DIR"
echo "  Config:  $BASE_CONFIG_DIR"
echo ""
echo "Permissions:"
ls -ld "$BASE_DATA_DIR" "$BASE_LOG_DIR" "$BASE_CONFIG_DIR"
echo ""
echo "Subdirectories:"
ls -ld "$BASE_DATA_DIR"/*
echo ""
log_info "All directories are owned by $SERVICE_USER:$SERVICE_GROUP with permissions 750"

