#!/bin/bash
# Debug script to check what settings are being loaded

sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<'EOF'
import os
import sys
from pathlib import Path
from dicom_gw.config.settings import get_settings

print("=== Environment Variables ===")
print(f"DATABASE_URL from env: {os.getenv('DATABASE_URL', 'NOT SET')}")

print("\n=== Checking Config Files ===")
config_files = [
    ".env",
    "/etc/dicom-gw/dicom-gw-api.env",
    "/etc/dicom-gw/dicom-gw-workers.env",
    "/etc/dicom-gw/config.yaml",
]

for config_file in config_files:
    path = Path(config_file)
    if path.exists():
        print(f"✓ {config_file} exists")
        if config_file.endswith('.env'):
            # Show first line (hide password)
            with open(path) as f:
                first_line = f.readline().strip()
                if 'DATABASE_URL' in first_line:
                    parts = first_line.split('@')
                    if len(parts) > 1:
                        print(f"  First line: {parts[0].split(':')[-1]}@...")
                    else:
                        print(f"  First line: {first_line[:50]}...")
    else:
        print(f"✗ {config_file} does not exist")

print("\n=== Settings Object ===")
settings = get_settings()
print(f"Database URL: {settings.database_url}")
print(f"Database URL (masked): {settings.database_url.split('@')[0] if '@' in settings.database_url else settings.database_url}@...")

# Check if password is in URL
if '@' in settings.database_url:
    parts = settings.database_url.split('@')
    if len(parts) > 0:
        user_pass = parts[0].split('://')[-1]
        if ':' in user_pass:
            user, password = user_pass.split(':', 1)
            print(f"Username: {user}")
            print(f"Password present: {'YES' if password else 'NO'} (length: {len(password) if password else 0})")
        else:
            print(f"User only: {user_pass}")
EOF

