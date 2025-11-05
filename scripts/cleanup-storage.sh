#!/bin/bash
# Cleanup script for DICOM Gateway storage
# Removes temporary files and old data (with safety checks)

set -e

# Configuration
BASE_DATA_DIR="/var/lib/dicom-gw"
SERVICE_USER="dicom-gw"
DAYS_TO_KEEP_TMP=7
DAYS_TO_KEEP_FAILED=90
DAYS_TO_KEEP_FORWARDED=365

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

# Check if running as root or service user
if [ "$EUID" -ne 0 ] && [ "$(whoami)" != "$SERVICE_USER" ]; then 
    log_error "Please run as root (use sudo) or as $SERVICE_USER"
    exit 1
fi

# Function to safely remove old files
cleanup_old_files() {
    local dir="$1"
    local days="$2"
    local description="$3"
    
    if [ ! -d "$dir" ]; then
        log_warn "Directory does not exist: $dir"
        return
    fi
    
    log_info "Cleaning up $description older than $days days in $dir"
    
    # Count files before cleanup
    local count_before=$(find "$dir" -type f -mtime +$days 2>/dev/null | wc -l)
    
    if [ "$count_before" -gt 0 ]; then
        log_info "Found $count_before file(s) to remove"
        
        # Remove files
        find "$dir" -type f -mtime +$days -delete 2>/dev/null
        
        # Remove empty directories
        find "$dir" -type d -empty -delete 2>/dev/null
        
        log_info "Cleaned up $description in $dir"
    else
        log_info "No $description files older than $days days found"
    fi
}

log_info "Starting DICOM Gateway storage cleanup"

# Cleanup temporary files
cleanup_old_files "$BASE_DATA_DIR/tmp" "$DAYS_TO_KEEP_TMP" "temporary files"

# Cleanup failed forwarding attempts
cleanup_old_files "$BASE_DATA_DIR/failed" "$DAYS_TO_KEEP_FAILED" "failed forwarding attempts"

# Cleanup forwarded studies (optional - be careful here)
# Uncomment if you want automatic cleanup of forwarded studies
# cleanup_old_files "$BASE_DATA_DIR/forwarded" "$DAYS_TO_KEEP_FORWARDED" "forwarded studies"

# Cleanup queue directory (remove stale files)
if [ -d "$BASE_DATA_DIR/queue" ]; then
    log_info "Cleaning up queue directory..."
    find "$BASE_DATA_DIR/queue" -type f -mtime +1 -delete 2>/dev/null || true
fi

# Cleanup incoming directory (remove stale files)
if [ -d "$BASE_DATA_DIR/incoming" ]; then
    log_info "Cleaning up incoming directory..."
    find "$BASE_DATA_DIR/incoming" -type f -mtime +1 -delete 2>/dev/null || true
fi

# Display disk usage
log_info "Disk usage after cleanup:"
if [ -d "$BASE_DATA_DIR" ]; then
    du -sh "$BASE_DATA_DIR"/* 2>/dev/null | sort -h || true
    echo ""
    df -h "$BASE_DATA_DIR"
fi

log_info "Storage cleanup completed"

