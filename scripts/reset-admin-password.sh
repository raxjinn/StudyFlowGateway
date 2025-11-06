#!/bin/bash
# Script to reset admin password to a known value

set -e

USERNAME="${1:-admin}"
NEW_PASSWORD="${2:-admin123}"

echo "Resetting password for user: $USERNAME"
echo "New password: $NEW_PASSWORD"

sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<EOF
import asyncio
from sqlalchemy import select
from dicom_gw.config.settings import get_settings
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import hash_password

async def reset_password():
    settings = get_settings()
    username = "$USERNAME"
    new_password = "$NEW_PASSWORD"
    
    async for session in get_db_session():
        # Find the user
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"✗ User '{username}' not found")
            return
        
        # Reset password and unlock account
        print(f"\n🔄 Resetting password for '{username}'...")
        user.password_hash = hash_password(new_password)
        user.locked_until = None
        user.failed_login_attempts = 0
        await session.commit()
        
        print(f"✓ Password reset successfully!")
        print(f"\nLogin credentials:")
        print(f"  - Username: {username}")
        print(f"  - Password: {new_password}")
        print(f"  - Account unlocked")
        print(f"  - Failed attempts reset to 0")
        break

if __name__ == "__main__":
    asyncio.run(reset_password())
EOF

