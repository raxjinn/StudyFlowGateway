#!/bin/bash
# Script to check RPM build process and diagnose issues

BUILD_DIR="${HOME}/rpmbuild"
TARBALL="${BUILD_DIR}/SOURCES/dicom-gateway-0.1.0.tar.gz"

echo "=== Checking RPM Build Environment ==="
echo ""

echo "1. Checking tarball contents:"
if [ -f "$TARBALL" ]; then
    echo "   Tarball exists: $TARBALL"
    echo "   Checking for scripts in tarball:"
    tar -tzf "$TARBALL" | grep "scripts/" | head -10
    echo ""
    echo "   Checking for systemd template files in tarball:"
    tar -tzf "$TARBALL" | grep "systemd.*@\.service" | head -10
else
    echo "   ERROR: Tarball not found: $TARBALL"
fi
echo ""

echo "2. Checking BUILD directory:"
BUILD_EXTRACTED="${BUILD_DIR}/BUILD/dicom-gateway-0.1.0"
if [ -d "$BUILD_EXTRACTED" ]; then
    echo "   BUILD directory exists: $BUILD_EXTRACTED"
    echo "   Checking for scripts:"
    ls -la "$BUILD_EXTRACTED/scripts/" 2>&1 | head -10 || echo "   scripts/ directory not found"
    echo ""
    echo "   Checking for systemd template files:"
    ls -la "$BUILD_EXTRACTED/systemd/"*@.service 2>&1 | head -10 || echo "   Template service files not found"
else
    echo "   BUILD directory not found: $BUILD_EXTRACTED"
fi
echo ""

echo "3. Checking BUILDROOT directory:"
BUILDROOT_DIR="${BUILD_DIR}/BUILDROOT/dicom-gateway-0.1.0-1.el10.x86_64"
if [ -d "$BUILDROOT_DIR" ]; then
    echo "   BUILDROOT directory exists: $BUILDROOT_DIR"
    echo "   Checking for scripts in BUILDROOT:"
    ls -la "$BUILDROOT_DIR/opt/dicom-gw/scripts/" 2>&1 | head -10 || echo "   scripts/ not copied to BUILDROOT"
    echo ""
    echo "   Checking for systemd template files in BUILDROOT:"
    ls -la "$BUILDROOT_DIR/usr/lib/systemd/system/"*@.service 2>&1 | head -10 || echo "   Template service files not copied to BUILDROOT"
else
    echo "   BUILDROOT directory not found: $BUILDROOT_DIR"
    echo "   (This is normal if RPM hasn't been built yet)"
fi
echo ""

echo "4. Checking source repository:"
if [ -d "scripts" ]; then
    echo "   scripts/ directory exists in source"
    echo "   Script files:"
    ls -1 scripts/*.sh 2>/dev/null || echo "   No .sh files found"
else
    echo "   ERROR: scripts/ directory not found in source"
fi
echo ""

if [ -d "systemd" ]; then
    echo "   systemd/ directory exists in source"
    echo "   Template service files:"
    ls -1 systemd/*@.service 2>/dev/null || echo "   No @.service files found"
else
    echo "   ERROR: systemd/ directory not found in source"
fi

