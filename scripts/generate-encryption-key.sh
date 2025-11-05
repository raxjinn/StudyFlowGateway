#!/bin/bash
# Generate encryption key for database encryption

set -e

KEY_FILE="${1:-/etc/dicom-gw/db-encryption.key}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_warn "Not running as root. Key file may not be created with correct permissions."
fi

# Create directory if it doesn't exist
mkdir -p "$(dirname "$KEY_FILE")"

# Generate encryption key (32 bytes, base64 encoded)
log_info "Generating encryption key..."
KEY=$(openssl rand -base64 32)

# Save to file
echo "$KEY" > "$KEY_FILE"
chmod 400 "$KEY_FILE"

if [ "$EUID" -eq 0 ]; then
    # Try to set ownership to dicom-gw user if it exists
    if id "dicom-gw" &>/dev/null; then
        chown dicom-gw:dicom-gw "$KEY_FILE"
    fi
fi

log_info "Encryption key generated: $KEY_FILE"
log_warn "IMPORTANT: Add this to your environment configuration:"
echo "export DICOM_GW_DB_ENCRYPTION_KEY=\"$KEY\""
echo ""
log_warn "Or add to /etc/dicom-gw/dicom-gw-api.service:"
echo "Environment=\"DICOM_GW_DB_ENCRYPTION_KEY=$KEY\""

