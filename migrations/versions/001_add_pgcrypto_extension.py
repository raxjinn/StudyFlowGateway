"""Add pgcrypto extension for database encryption.

Revision ID: 001_add_pgcrypto
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_pgcrypto'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgcrypto extension for database encryption."""
    # Enable pgcrypto extension
    # Note: This requires superuser privileges
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    """Disable pgcrypto extension."""
    # Note: Only drop if no encrypted data exists
    # op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    pass  # Don't drop extension in downgrade to avoid data loss

