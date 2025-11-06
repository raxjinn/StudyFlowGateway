#!/bin/bash
# Script to create an admin user for DICOM Gateway

set -e

# Configuration
USERNAME="${1:-admin}"
PASSWORD="${2:-}"
EMAIL="${3:-admin@example.com}"

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

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Check if password is provided
if [ -z "$PASSWORD" ]; then
    log_error "Usage: $0 <username> <password> [email]"
    echo "  username: Login username (default: admin)"
    echo "  password: Login password (required)"
    echo "  email: Email address (default: admin@example.com)"
    exit 1
fi

log_info "Creating admin user: $USERNAME"

# Create Python script to create admin user
sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<EOF
import asyncio
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import hash_password
from sqlalchemy import select

async def create_admin():
    username = "$USERNAME"
    password = "$PASSWORD"
    email = "$EMAIL"
    
    async for session in get_db_session():
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User '{username}' already exists!")
            print(f"To reset password, use the API or update the user directly.")
            return
        
        # Create new admin user
        admin = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            enabled=True
        )
        session.add(admin)
        await session.commit()
        print(f"✓ Admin user created successfully!")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"  Role: admin")
        print(f"  Password: [hidden]")
        print(f"")
        print(f"Please change the password after first login!")

asyncio.run(create_admin())
EOF

if [ $? -eq 0 ]; then
    log_info "Admin user created successfully!"
    log_warn "Please change the password after first login!"
else
    log_error "Failed to create admin user"
    exit 1
fi

