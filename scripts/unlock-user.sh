#!/bin/bash
# Script to unlock a user account in the DICOM Gateway database

set -e

USERNAME="${1:-admin}"

echo "Unlocking user account: $USERNAME"

sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<EOF
import asyncio
from sqlalchemy import select, update
from dicom_gw.config.settings import get_settings
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User

async def unlock_user():
    settings = get_settings()
    username = "$USERNAME"
    
    async for session in get_db_session():
        # Find the user
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"✗ User '{username}' not found")
            return
        
        # Unlock the account
        user.locked_until = None
        user.failed_login_attempts = 0
        await session.commit()
        
        print(f"✓ User '{username}' unlocked successfully")
        print(f"  - Failed login attempts: {user.failed_login_attempts}")
        print(f"  - Locked until: {user.locked_until}")
        break

if __name__ == "__main__":
    asyncio.run(unlock_user())
EOF

