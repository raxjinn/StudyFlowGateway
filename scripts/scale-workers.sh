#!/bin/bash
# Script to scale worker instances horizontally
#
# Usage:
#   ./scale-workers.sh queue 3        # Scale to 3 queue workers
#   ./scale-workers.sh forwarder 5    # Scale to 5 forwarder workers
#   ./scale-workers.sh dbpool 2       # Scale to 2 dbpool workers
#   ./scale-workers.sh all            # Show current worker counts

set -euo pipefail

WORKER_TYPE="${1:-all}"
TARGET_COUNT="${2:-}"

SYSTEMD_DIR="/usr/lib/systemd/system"
WORKER_TYPES=("queue" "forwarder" "dbpool")

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

get_current_count() {
    local worker_type=$1
    local service_pattern="dicom-gw-${worker_type}-worker@"
    
    # Count active instances
    systemctl list-units --type=service --state=running,active 2>/dev/null | \
        grep -c "${service_pattern}" || echo "0"
}

get_enabled_count() {
    local worker_type=$1
    local service_pattern="dicom-gw-${worker_type}-worker@"
    
    # Count enabled instances
    systemctl list-unit-files --type=service --state=enabled 2>/dev/null | \
        grep -c "${service_pattern}" || echo "0"
}

scale_worker() {
    local worker_type=$1
    local target_count=$2
    local current_count
    
    current_count=$(get_current_count "$worker_type")
    
    log_info "Scaling ${worker_type} workers: ${current_count} -> ${target_count}"
    
    if [ "$target_count" -lt 0 ] || [ "$target_count" -gt 100 ]; then
        log_error "Invalid target count: ${target_count} (must be 0-100)"
        return 1
    fi
    
    # Stop instances beyond target
    if [ "$current_count" -gt "$target_count" ]; then
        local stop_count=$((current_count - target_count))
        log_info "Stopping ${stop_count} ${worker_type} worker instance(s)..."
        
        for ((i=target_count; i<current_count; i++)); do
            local instance_id="${i}"
            log_info "Stopping dicom-gw-${worker_type}-worker@${instance_id}..."
            systemctl stop "dicom-gw-${worker_type}-worker@${instance_id}" || true
            systemctl disable "dicom-gw-${worker_type}-worker@${instance_id}" || true
        done
    fi
    
    # Start instances up to target
    if [ "$target_count" -gt "$current_count" ]; then
        local start_count=$((target_count - current_count))
        log_info "Starting ${start_count} ${worker_type} worker instance(s)..."
        
        for ((i=current_count; i<target_count; i++)); do
            local instance_id="${i}"
            log_info "Starting dicom-gw-${worker_type}-worker@${instance_id}..."
            systemctl enable "dicom-gw-${worker_type}-worker@${instance_id}" || true
            systemctl start "dicom-gw-${worker_type}-worker@${instance_id}" || true
        done
    fi
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    # Wait a moment for services to start
    sleep 2
    
    # Verify
    local new_count
    new_count=$(get_current_count "$worker_type")
    
    if [ "$new_count" -eq "$target_count" ]; then
        log_info "Successfully scaled ${worker_type} workers to ${target_count}"
        return 0
    else
        log_warn "Expected ${target_count} ${worker_type} workers, but ${new_count} are running"
        return 1
    fi
}

show_status() {
    log_info "Current worker status:"
    echo ""
    
    for worker_type in "${WORKER_TYPES[@]}"; do
        local running_count
        local enabled_count
        running_count=$(get_current_count "$worker_type")
        enabled_count=$(get_enabled_count "$worker_type")
        
        echo "  ${worker_type}:"
        echo "    Running: ${running_count}"
        echo "    Enabled: ${enabled_count}"
        echo ""
    done
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

# Check if template service files exist
for worker_type in "${WORKER_TYPES[@]}"; do
    if [ ! -f "${SYSTEMD_DIR}/dicom-gw-${worker_type}-worker@.service" ]; then
        log_error "Template service file not found: ${SYSTEMD_DIR}/dicom-gw-${worker_type}-worker@.service"
        log_error "Please install the systemd service files first"
        exit 1
    fi
done

# Handle different commands
case "$WORKER_TYPE" in
    all)
        show_status
        ;;
    queue|forwarder|dbpool)
        if [ -z "$TARGET_COUNT" ]; then
            log_error "Target count required for worker type: ${WORKER_TYPE}"
            log_error "Usage: $0 ${WORKER_TYPE} <count>"
            exit 1
        fi
        
        if ! [[ "$TARGET_COUNT" =~ ^[0-9]+$ ]]; then
            log_error "Invalid count: ${TARGET_COUNT} (must be a number)"
            exit 1
        fi
        
        scale_worker "$WORKER_TYPE" "$TARGET_COUNT"
        ;;
    *)
        log_error "Unknown worker type: ${WORKER_TYPE}"
        log_error "Valid types: queue, forwarder, dbpool, all"
        exit 1
        ;;
esac

