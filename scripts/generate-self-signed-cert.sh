#!/bin/bash
# Generate self-signed SSL certificate for development/testing

set -e

# Configuration
CERT_DIR="/etc/dicom-gw/tls"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"
DOMAIN="${1:-localhost}"
DAYS="${2:-365}"

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

log_info "Generating self-signed certificate for $DOMAIN (valid for $DAYS days)"

# Create certificate directory
mkdir -p "$CERT_DIR"
chmod 750 "$CERT_DIR"

# Generate private key
log_info "Generating private key..."
openssl genrsa -out "$KEY_FILE" 2048
chmod 600 "$KEY_FILE"

# Generate certificate
log_info "Generating certificate..."
openssl req -new -x509 -key "$KEY_FILE" -out "$CERT_FILE" -days "$DAYS" \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:*.$DOMAIN,IP:127.0.0.1,IP:::1"

chmod 644 "$CERT_FILE"

log_info "Certificate generated successfully!"
log_info "Certificate: $CERT_FILE"
log_info "Private key: $KEY_FILE"
log_warn "This is a self-signed certificate for development/testing only!"
log_warn "For production, use Let's Encrypt or a proper CA-signed certificate."

# Set ownership
if id "dicom-gw" &>/dev/null; then
    chown -R dicom-gw:dicom-gw "$CERT_DIR"
    log_info "Set ownership to dicom-gw user"
fi

