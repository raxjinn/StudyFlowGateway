#!/bin/bash
# Setup script for building DICOM Gateway RPM on Rocky Linux
# Detects available Python version and installs appropriate dependencies

set -e

echo "Setting up build dependencies for DICOM Gateway RPM..."

# Detect Rocky Linux version
if [ -f /etc/rocky-release ]; then
    ROCKY_VERSION=$(grep -oP 'Rocky Linux release \K[0-9]+' /etc/rocky-release)
    echo "Detected Rocky Linux $ROCKY_VERSION"
else
    echo "Warning: Rocky Linux not detected, proceeding anyway..."
    ROCKY_VERSION=8
fi

# Install basic build tools
echo "Installing RPM build tools..."
sudo dnf install -y rpm-build rpmdevtools make gcc gcc-c++ openssl-devel

# Check and install Python
echo "Checking Python availability..."
if dnf list available python3.11 python3.11-devel 2>/dev/null | grep -q python3.11; then
    echo "Installing Python 3.11..."
    sudo dnf install -y python3.11 python3.11-devel python3-pip
    PYTHON_VERSION=3.11
elif dnf list available python39 python39-devel 2>/dev/null | grep -q python39; then
    echo "Installing Python 3.9..."
    sudo dnf module reset python39 2>/dev/null || true
    sudo dnf module enable python39 -y
    sudo dnf install -y python39 python39-devel python39-pip
    PYTHON_VERSION=3.9
elif dnf list available python38 python38-devel 2>/dev/null | grep -q python38; then
    echo "Installing Python 3.8..."
    sudo dnf module reset python38 2>/dev/null || true
    sudo dnf module enable python38 -y
    sudo dnf install -y python38 python38-devel python38-pip
    PYTHON_VERSION=3.8
else
    echo "Installing system Python 3..."
    sudo dnf install -y python3 python3-devel python3-pip
    PYTHON_VERSION=$(python3 --version | grep -oP 'Python \K[0-9]+\.[0-9]+')
fi

echo "Python $PYTHON_VERSION will be used"

# Install PostgreSQL development headers
echo "Checking PostgreSQL availability..."
if dnf list available postgresql14-devel 2>/dev/null | grep -q postgresql14-devel; then
    echo "Installing PostgreSQL 14 development headers..."
    sudo dnf install -y postgresql14-devel
elif dnf list available postgresql13-devel 2>/dev/null | grep -q postgresql13-devel; then
    echo "Installing PostgreSQL 13 development headers..."
    sudo dnf install -y postgresql13-devel
elif dnf list available postgresql12-devel 2>/dev/null | grep -q postgresql12-devel; then
    echo "Installing PostgreSQL 12 development headers..."
    sudo dnf install -y postgresql12-devel
else
    echo "Installing PostgreSQL development headers (default version)..."
    sudo dnf install -y postgresql postgresql-devel
fi

# Install Node.js for frontend build
echo "Installing Node.js..."
if ! command -v node &> /dev/null; then
    echo "Installing Node.js 20.x LTS from NodeSource..."
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
    sudo dnf install -y nodejs
else
    echo "Node.js already installed: $(node --version)"
fi

# Setup RPM build directory
echo "Setting up RPM build directory..."
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Update spec file if needed for different Python version
if [ "$PYTHON_VERSION" != "3.11" ]; then
    echo "Updating spec file for Python $PYTHON_VERSION..."
    SPEC_FILE="rpm/dicom-gateway.spec"
    if [ -f "$SPEC_FILE" ]; then
        sed -i "s/python_version 3.11/python_version $PYTHON_VERSION/" "$SPEC_FILE"
        sed -i "s/%{python_pkg} >= 3.11/%{python_pkg} >= ${PYTHON_VERSION}/" "$SPEC_FILE"
        echo "Spec file updated for Python $PYTHON_VERSION"
    fi
fi

echo ""
echo "✓ Build dependencies installed successfully!"
echo ""
echo "Python version: $PYTHON_VERSION"
echo "Node.js version: $(node --version 2>/dev/null || echo 'Not installed')"
echo ""
echo "Next steps:"
echo "  1. cd rpm"
echo "  2. make rpm"
echo ""

