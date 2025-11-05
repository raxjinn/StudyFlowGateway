#!/bin/bash
# Setup script for Nginx reverse proxy configuration

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

log_info "Setting up Nginx reverse proxy for DICOM Gateway"

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    log_info "Installing Nginx..."
    if command -v dnf &> /dev/null; then
        dnf install -y nginx
    elif command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y nginx
    else
        log_error "Cannot install Nginx. Please install manually."
        exit 1
    fi
fi

# Create configuration directory if it doesn't exist
mkdir -p /etc/nginx/conf.d

# Copy configuration file
CONFIG_FILE="/etc/nginx/conf.d/dicom-gateway.conf"
if [ -f "$CONFIG_FILE" ]; then
    log_warn "Configuration file already exists: $CONFIG_FILE"
    read -p "Backup existing file and continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backed up existing configuration"
    else
        log_info "Aborted"
        exit 1
    fi
fi

# Find the script directory and nginx config
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
NGINX_CONFIG="$PROJECT_DIR/nginx/dicom-gateway.conf"

if [ ! -f "$NGINX_CONFIG" ]; then
    log_error "Nginx configuration file not found: $NGINX_CONFIG"
    exit 1
fi

# Copy configuration
cp "$NGINX_CONFIG" "$CONFIG_FILE"
log_info "Copied Nginx configuration to $CONFIG_FILE"

# Prompt for domain name
read -p "Enter domain name (or press Enter to use default): " DOMAIN
if [ -n "$DOMAIN" ]; then
    sed -i "s/server_name _;/server_name $DOMAIN;/g" "$CONFIG_FILE"
    log_info "Updated server_name to $DOMAIN"
fi

# Create frontend directory
FRONTEND_DIR="/var/www/dicom-gateway"
mkdir -p "$FRONTEND_DIR"
chown -R nginx:nginx "$FRONTEND_DIR" 2>/dev/null || chown -R www-data:www-data "$FRONTEND_DIR" 2>/dev/null || true
log_info "Created frontend directory: $FRONTEND_DIR"
log_warn "Remember to build and copy the Vue.js frontend to this directory"

# Create log directory
mkdir -p /var/log/nginx
log_info "Log directory ready: /var/log/nginx"

# Check SSL certificates
CERT_DIR="/etc/dicom-gw/tls"
if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    log_warn "SSL certificates not found in $CERT_DIR"
    log_warn "Please set up TLS certificates before starting Nginx"
    log_warn "See: scripts/setup-letsencrypt.sh or docs/tls-setup.md"
else
    log_info "SSL certificates found"
fi

# Test configuration
log_info "Testing Nginx configuration..."
if nginx -t; then
    log_info "Configuration test passed"
else
    log_error "Configuration test failed. Please fix errors and try again."
    exit 1
fi

# Configure firewall
log_info "Configuring firewall..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=http 2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    log_info "Firewall configured (firewalld)"
elif command -v ufw &> /dev/null; then
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
    log_info "Firewall configured (ufw)"
else
    log_warn "Firewall not configured. Please manually allow ports 80 and 443"
fi

# Enable and start Nginx
log_info "Enabling Nginx service..."
systemctl enable nginx

log_info "Starting Nginx..."
if systemctl start nginx; then
    log_info "Nginx started successfully"
else
    log_error "Failed to start Nginx. Check logs: sudo journalctl -u nginx"
    exit 1
fi

# Check status
if systemctl is-active --quiet nginx; then
    log_info "Nginx is running"
    log_info "Configuration file: $CONFIG_FILE"
    log_info "Frontend directory: $FRONTEND_DIR"
    log_info "Access logs: /var/log/nginx/dicom-gateway-access.log"
    log_info "Error logs: /var/log/nginx/dicom-gateway-error.log"
    echo ""
    log_warn "Next steps:"
    echo "  1. Build and copy Vue.js frontend to $FRONTEND_DIR"
    echo "  2. Ensure SSL certificates are in $CERT_DIR"
    echo "  3. Update server_name in $CONFIG_FILE if needed"
    echo "  4. Test: curl https://$DOMAIN/api/v1/health"
else
    log_error "Nginx is not running. Check status: sudo systemctl status nginx"
    exit 1
fi

