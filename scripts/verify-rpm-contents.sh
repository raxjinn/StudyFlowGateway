#!/bin/bash
# Script to verify RPM contents before/after installation

RPM_FILE="${1:-/root/rpmbuild/RPMS/noarch/dicom-gateway-*.rpm}"

echo "=== Checking RPM File ==="
if [ ! -f $RPM_FILE ]; then
    echo "Error: RPM file not found: $RPM_FILE"
    echo "Available RPMs:"
    ls -la /root/rpmbuild/RPMS/noarch/dicom-gateway-*.rpm 2>/dev/null || echo "  No RPM files found"
    exit 1
fi

echo "RPM file: $RPM_FILE"
echo ""

echo "=== Checking for Template Service Files in RPM ==="
rpm -qlp $RPM_FILE | grep -E "dicom-gw-.*-worker@\.service" || echo "  NOT FOUND in RPM"
echo ""

echo "=== Checking for Scaling Script in RPM ==="
rpm -qlp $RPM_FILE | grep "scale-workers.sh" || echo "  NOT FOUND in RPM"
echo ""

echo "=== Checking Source Files ==="
if [ -d "systemd" ]; then
    echo "Template service files in source:"
    ls -1 systemd/*@.service 2>/dev/null || echo "  NOT FOUND in source"
else
    echo "systemd directory not found in current directory"
fi

if [ -f "scripts/scale-workers.sh" ]; then
    echo "scale-workers.sh exists in source: YES"
else
    echo "scale-workers.sh exists in source: NO"
fi
echo ""

echo "=== Checking Installed Files ==="
echo "Template service files installed:"
ls -1 /usr/lib/systemd/system/dicom-gw-*-worker@.service 2>/dev/null || echo "  NOT INSTALLED"
echo ""

echo "Scaling script installed:"
ls -la /opt/dicom-gw/scripts/scale-workers.sh 2>/dev/null || echo "  NOT INSTALLED"

