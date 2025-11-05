#!/bin/bash
# Verification script for DICOM Gateway storage layout
# Checks that all directories exist with correct permissions

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

ERRORS=0
WARNINGS=0

check_directory() {
    local dir="$1"
    local expected_perm="$2"
    local expected_user="$3"
    local expected_group="$4"
    
    if [ ! -d "$dir" ]; then
        log_error "Directory does not exist: $dir"
        ((ERRORS++))
        return 1
    fi
    
    local perm=$(stat -c "%a" "$dir")
    local user=$(stat -c "%U" "$dir")
    local group=$(stat -c "%G" "$dir")
    
    if [ "$perm" != "$expected_perm" ]; then
        log_error "Incorrect permissions for $dir: expected $expected_perm, found $perm"
        ((ERRORS++))
    else
        log_info "Permissions OK: $dir ($perm)"
    fi
    
    if [ "$user" != "$expected_user" ]; then
        log_warn "Incorrect owner for $dir: expected $expected_user, found $user"
        ((WARNINGS++))
    else
        log_info "Owner OK: $dir ($user)"
    fi
    
    if [ "$group" != "$expected_group" ]; then
        log_warn "Incorrect group for $dir: expected $expected_group, found $group"
        ((WARNINGS++))
    else
        log_info "Group OK: $dir ($group)"
    fi
}

check_user() {
    if ! id -u "$SERVICE_USER" &>/dev/null; then
        log_error "Service user does not exist: $SERVICE_USER"
        ((ERRORS++))
        return 1
    fi
    
    log_info "Service user exists: $SERVICE_USER"
    return 0
}

log_info "Verifying DICOM Gateway storage layout"

# Check service user
check_user

# Check base directories
log_info "Checking base directories..."
check_directory "$BASE_DATA_DIR" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_LOG_DIR" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_CONFIG_DIR" "750" "$SERVICE_USER" "$SERVICE_GROUP"

# Check data subdirectories
log_info "Checking data subdirectories..."
check_directory "$BASE_DATA_DIR/storage" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_DATA_DIR/incoming" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_DATA_DIR/queue" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_DATA_DIR/forwarded" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_DATA_DIR/failed" "750" "$SERVICE_USER" "$SERVICE_GROUP"
check_directory "$BASE_DATA_DIR/tmp" "750" "$SERVICE_USER" "$SERVICE_GROUP"

# Check config subdirectories
log_info "Checking config subdirectories..."
check_directory "$BASE_CONFIG_DIR/tls" "750" "$SERVICE_USER" "$SERVICE_GROUP"

# Check disk space
log_info "Checking disk space..."
if [ -d "$BASE_DATA_DIR" ]; then
    AVAILABLE=$(df -h "$BASE_DATA_DIR" | awk 'NR==2 {print $4}')
    USED=$(df -h "$BASE_DATA_DIR" | awk 'NR==2 {print $3}')
    USE_PCT=$(df -h "$BASE_DATA_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    
    log_info "Disk space - Used: $USED, Available: $AVAILABLE, Usage: $USE_PCT%"
    
    if [ "$USE_PCT" -gt 90 ]; then
        log_error "Disk usage is above 90%: $USE_PCT%"
        ((ERRORS++))
    elif [ "$USE_PCT" -gt 80 ]; then
        log_warn "Disk usage is above 80%: $USE_PCT%"
        ((WARNINGS++))
    fi
fi

# Check SELinux context (if SELinux is enabled)
if command -v getenforce >/dev/null 2>&1; then
    if [ "$(getenforce)" != "Disabled" ]; then
        log_info "SELinux is enabled, checking contexts..."
        # SELinux contexts should be set appropriately
        # This is a basic check - may need adjustment based on your SELinux policy
        log_info "SELinux status: $(getenforce)"
    fi
fi

# Summary
echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    log_info "Verification completed successfully - no issues found!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    log_warn "Verification completed with $WARNINGS warning(s)"
    exit 0
else
    log_error "Verification failed with $ERRORS error(s) and $WARNINGS warning(s)"
    exit 1
fi

