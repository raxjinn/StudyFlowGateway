#!/bin/bash
# Test database connection script

# Load environment variables from the service file
if [ -f /etc/dicom-gw/dicom-gw-api.env ]; then
    set -a
    source /etc/dicom-gw/dicom-gw-api.env
    set +a
fi

# Run the test
sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<'PYEOF'
import os
import asyncio
from sqlalchemy import text
from dicom_gw.config.settings import get_settings
from dicom_gw.database.connection import get_db_session

async def test():
    settings = get_settings()
    # Show database URL (hide password)
    db_url_parts = settings.database_url.split('@')
    if len(db_url_parts) > 1:
        print(f"Database URL: {db_url_parts[0]}@...")
    else:
        print(f"Database URL: {settings.database_url}")
    
    try:
        async for session in get_db_session():
            # Use text() for raw SQL in SQLAlchemy 2.x
            result = await session.execute(text("SELECT version();"))
            version = result.scalar()
            print("✓ Database connection successful!")
            print(f"PostgreSQL version: {version}")
            break
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
PYEOF

