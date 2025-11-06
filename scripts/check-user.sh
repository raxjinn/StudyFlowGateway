#!/bin/bash
# Script to check user info and optionally reset password in the DICOM Gateway database

set -e

USERNAME="${1:-admin}"
ACTION="${2:-check}"

echo "Checking user: $USERNAME"

sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<EOF
import asyncio
from sqlalchemy import select
from dicom_gw.config.settings import get_settings
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import hash_password

async def check_user():
    settings = get_settings()
    username = "$USERNAME"
    action = "$ACTION"
    
    async for session in get_db_session():
        # Find the user
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"✗ User '{username}' not found")
            return
        
        # Display user info
        print(f"\n✓ User '{username}' found:")
        print(f"  - ID: {user.id}")
        print(f"  - Username: {user.username}")
        print(f"  - Email: {user.email or 'None'}")
        print(f"  - Role: {user.role}")
        print(f"  - Enabled: {user.enabled}")
        print(f"  - Locked until: {user.locked_until or 'Not locked'}")
        print(f"  - Failed login attempts: {user.failed_login_attempts}")
        print(f"  - Last login: {user.last_login_at or 'Never'}")
        print(f"  - Password hash: {user.password_hash[:50]}...")
        
        if action == "reset":
            new_password = "admin123"
            print(f"\n🔄 Resetting password to: {new_password}")
            user.password_hash = hash_password(new_password)
            user.locked_until = None
            user.failed_login_attempts = 0
            await session.commit()
            print(f"✓ Password reset successfully!")
            print(f"  - Username: {username}")
            print(f"  - Password: {new_password}")
            print(f"  - Account unlocked")
        elif action == "unlock":
            print(f"\n🔓 Unlocking account...")
            user.locked_until = None
            user.failed_login_attempts = 0
            await session.commit()
            print(f"✓ Account unlocked successfully!")
        
        break

if __name__ == "__main__":
    asyncio.run(check_user())
EOF

