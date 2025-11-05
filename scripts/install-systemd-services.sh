#!/bin/bash
# Installation script for systemd service files

set -e

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

log_info "Installing DICOM Gateway systemd services"

# Find script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
SYSTEMD_DIR="$PROJECT_DIR/systemd"

if [ ! -d "$SYSTEMD_DIR" ]; then
    log_error "Systemd directory not found: $SYSTEMD_DIR"
    exit 1
fi

# Create dicom-gw user if it doesn't exist
if ! id "dicom-gw" &>/dev/null; then
    log_info "Creating dicom-gw user..."
    useradd -r -s /bin/false -d /opt/dicom-gw dicom-gw
    log_info "Created dicom-gw user"
else
    log_info "User dicom-gw already exists"
fi

# Create necessary directories
log_info "Creating directories..."
mkdir -p /opt/dicom-gw
mkdir -p /var/lib/dicom-gw
mkdir -p /var/log/dicom-gw
mkdir -p /etc/dicom-gw

# Set ownership
chown -R dicom-gw:dicom-gw /opt/dicom-gw
chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
chown -R dicom-gw:dicom-gw /var/log/dicom-gw
chown -R dicom-gw:dicom-gw /etc/dicom-gw

# Set permissions
chmod 750 /opt/dicom-gw
chmod 750 /var/lib/dicom-gw
chmod 750 /var/log/dicom-gw
chmod 750 /etc/dicom-gw

log_info "Directories created and permissions set"

# Copy service files
log_info "Copying service files..."
cp "$SYSTEMD_DIR"/*.service /etc/systemd/system/
cp "$SYSTEMD_DIR"/*.target /etc/systemd/system/
log_info "Service files copied to /etc/systemd/system/"

# Create example environment files if they don't exist
if [ ! -f /etc/dicom-gw/dicom-gw-api.env ]; then
    log_info "Creating example environment file: dicom-gw-api.env"
    cat > /etc/dicom-gw/dicom-gw-api.env <<EOF
# DICOM Gateway API Service Environment Variables
# Uncomment and configure as needed

# DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
# DICOM_GW_APP_ENV=production
# DICOM_GW_APP_DEBUG=false
# DICOM_GW_SECRET_KEY=your-secret-key-here
EOF
    chmod 640 /etc/dicom-gw/dicom-gw-api.env
    chown dicom-gw:dicom-gw /etc/dicom-gw/dicom-gw-api.env
fi

if [ ! -f /etc/dicom-gw/dicom-gw-workers.env ]; then
    log_info "Creating example environment file: dicom-gw-workers.env"
    cat > /etc/dicom-gw/dicom-gw-workers.env <<EOF
# DICOM Gateway Workers Environment Variables
# Uncomment and configure as needed

# DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
# DICOM_GW_APP_ENV=production
EOF
    chmod 640 /etc/dicom-gw/dicom-gw-workers.env
    chown dicom-gw:dicom-gw /etc/dicom-gw/dicom-gw-workers.env
fi

if [ ! -f /etc/dicom-gw/dicom-gw-scp.env ]; then
    log_info "Creating example environment file: dicom-gw-scp.env"
    cat > /etc/dicom-gw/dicom-gw-scp.env <<EOF
# DICOM Gateway SCP Service Environment Variables
# Uncomment and configure as needed

# DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
# DICOM_GW_DICOM_AE_TITLE=DICOMGW
# DICOM_GW_DICOM_PORT=104
EOF
    chmod 640 /etc/dicom-gw/dicom-gw-scp.env
    chown dicom-gw:dicom-gw /etc/dicom-gw/dicom-gw-scp.env
fi

# Reload systemd daemon
log_info "Reloading systemd daemon..."
systemctl daemon-reload

log_info "Systemd services installed successfully!"
log_info ""
log_info "Next steps:"
log_info "  1. Configure environment files in /etc/dicom-gw/"
log_info "  2. Ensure Python virtual environment is at /opt/dicom-gw/venv"
log_info "  3. Ensure application code is at /opt/dicom-gw"
log_info "  4. Enable services: sudo systemctl enable dicom-gw.target"
log_info "  5. Start services: sudo systemctl start dicom-gw.target"
log_info ""
log_info "To view service status:"
log_info "  sudo systemctl status dicom-gw.target"
log_info ""
log_info "To view logs:"
log_info "  sudo journalctl -u dicom-gw-api.service -f"

