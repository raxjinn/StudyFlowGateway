#!/bin/bash
# Setup script for Let's Encrypt certificate provisioning

set -e

# Configuration
DOMAIN="${1:-}"
EMAIL="${2:-}"
WEBROOT_PATH="${3:-}"
STAGING="${4:-false}"

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

# Check parameters
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    log_error "Usage: $0 <domain> <email> [webroot_path] [staging]"
    echo "  domain: Domain name for certificate"
    echo "  email: Email address for Let's Encrypt"
    echo "  webroot_path: (Optional) Web root path for HTTP-01 challenge"
    echo "  staging: (Optional) Use staging environment (true/false, default: false)"
    exit 1
fi

log_info "Setting up Let's Encrypt certificate for $DOMAIN"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    log_info "Installing certbot..."
    if command -v dnf &> /dev/null; then
        dnf install -y certbot
    elif command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y certbot
    else
        log_error "Cannot install certbot. Please install manually."
        exit 1
    fi
fi

# Prepare certbot command
CERTBOT_CMD="certbot certonly --non-interactive --agree-tos --email $EMAIL --keep-until-expiring"

if [ "$STAGING" = "true" ]; then
    CERTBOT_CMD="$CERTBOT_CMD --staging"
    log_warn "Using Let's Encrypt staging environment"
fi

if [ -n "$WEBROOT_PATH" ]; then
    log_info "Using webroot method: $WEBROOT_PATH"
    CERTBOT_CMD="$CERTBOT_CMD --webroot --webroot-path $WEBROOT_PATH -d $DOMAIN"
else
    log_info "Using standalone method (requires port 80 to be available)"
    CERTBOT_CMD="$CERTBOT_CMD --standalone -d $DOMAIN"
fi

# Run certbot
log_info "Provisioning certificate..."
if eval "$CERTBOT_CMD"; then
    log_info "Certificate provisioned successfully"
    
    # Copy certificates to DICOM Gateway directory
    CERT_DIR="/etc/dicom-gw/tls"
    mkdir -p "$CERT_DIR"
    chmod 750 "$CERT_DIR"
    
    LETSENCRYPT_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    LETSENCRYPT_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
    
    if [ -f "$LETSENCRYPT_CERT" ] && [ -f "$LETSENCRYPT_KEY" ]; then
        cp "$LETSENCRYPT_CERT" "$CERT_DIR/cert.pem"
        cp "$LETSENCRYPT_KEY" "$CERT_DIR/key.pem"
        
        chmod 644 "$CERT_DIR/cert.pem"
        chmod 600 "$CERT_DIR/key.pem"
        
        # Set ownership if dicom-gw user exists
        if id "dicom-gw" &>/dev/null; then
            chown dicom-gw:dicom-gw "$CERT_DIR"/*
        fi
        
        log_info "Certificates copied to $CERT_DIR"
        
        # Display certificate info
        log_info "Certificate information:"
        openssl x509 -in "$CERT_DIR/cert.pem" -noout -subject -issuer -dates
        
        # Set up automatic renewal
        log_info "Setting up automatic renewal..."
        
        # Create renewal service
        cat > /etc/systemd/system/dicom-gw-cert-renew.service <<EOF
[Unit]
Description=Renew DICOM Gateway Let's Encrypt Certificate
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --no-self-upgrade
ExecStartPost=/bin/cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/cert.pem
ExecStartPost=/bin/cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/key.pem
ExecStartPost=/bin/chmod 644 $CERT_DIR/cert.pem
ExecStartPost=/bin/chmod 600 $CERT_DIR/key.pem
ExecStartPost=/usr/bin/systemctl reload nginx 2>/dev/null || true
ExecStartPost=/usr/bin/systemctl restart dicom-gw-api 2>/dev/null || true
EOF
        
        # Create renewal timer
        cat > /etc/systemd/system/dicom-gw-cert-renew.timer <<EOF
[Unit]
Description=Renew DICOM Gateway Certificate Daily
Requires=dicom-gw-cert-renew.service

[Timer]
OnCalendar=daily
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
EOF
        
        systemctl daemon-reload
        systemctl enable dicom-gw-cert-renew.timer
        systemctl start dicom-gw-cert-renew.timer
        
        log_info "Automatic renewal configured"
        log_info "Certificate will be renewed daily if expiration is within 30 days"
        
    else
        log_error "Certificate files not found after provisioning"
        exit 1
    fi
else
    log_error "Certificate provisioning failed"
    exit 1
fi

log_info "Let's Encrypt setup completed successfully!"
log_info "Domain: $DOMAIN"
log_info "Certificate location: $CERT_DIR"
log_info "Check renewal status: systemctl status dicom-gw-cert-renew.timer"

