#!/bin/bash
# Build script for DICOM Gateway RPM
# Usage: ./scripts/build-rpm.sh [version] [release]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RPM_DIR="$PROJECT_ROOT/rpm"

# Version and release
VERSION="${1:-0.1.0}"
RELEASE="${2:-1}"

echo "Building DICOM Gateway RPM"
echo "Version: $VERSION"
echo "Release: $RELEASE"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/setup.py" ]; then
    echo "Error: Must run from project root or ensure setup.py exists"
    exit 1
fi

# Check for required tools
command -v rpmbuild >/dev/null 2>&1 || { echo "Error: rpmbuild not found. Install with: sudo dnf install rpm-build"; exit 1; }
command -v make >/dev/null 2>&1 || { echo "Error: make not found. Install with: sudo dnf install make"; exit 1; }

# Setup RPM build directory
echo "Setting up RPM build environment..."
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Update spec file with version if provided
if [ "$1" != "" ]; then
    echo "Updating version in spec file..."
    sed -i "s/^Version:.*/Version:        $VERSION/" "$RPM_DIR/dicom-gateway.spec"
    sed -i "s/^Release:.*/Release:        $RELEASE%{?dist}/" "$RPM_DIR/dicom-gateway.spec"
fi

# Build frontend (optional but recommended)
if [ -d "$PROJECT_ROOT/frontend" ]; then
    echo "Building frontend..."
    cd "$PROJECT_ROOT/frontend"
    if [ -f "package.json" ]; then
        if command -v npm >/dev/null 2>&1; then
            npm install
            npm run build
            echo "Frontend built successfully"
        else
            echo "Warning: npm not found, skipping frontend build"
        fi
    fi
    cd "$PROJECT_ROOT"
fi

# Build RPM using Makefile
echo "Building RPM..."
cd "$RPM_DIR"
make rpm VERSION="$VERSION" RELEASE="$RELEASE"

# Find the built RPM
RPM_FILE=$(find ~/rpmbuild/RPMS -name "dicom-gateway-${VERSION}-${RELEASE}*.rpm" 2>/dev/null | head -1)

if [ -n "$RPM_FILE" ]; then
    echo ""
    echo "✓ RPM built successfully!"
    echo "  Location: $RPM_FILE"
    echo "  Size: $(du -h "$RPM_FILE" | cut -f1)"
    echo ""
    echo "To install:"
    echo "  sudo rpm -ivh $RPM_FILE"
    echo ""
    echo "To verify:"
    echo "  rpm -qlp $RPM_FILE"
    echo "  rpm -qpR $RPM_FILE"
else
    echo "Error: RPM file not found"
    exit 1
fi

