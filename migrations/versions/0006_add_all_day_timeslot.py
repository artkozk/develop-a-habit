"""add all_day value to time_slot enum

Revision ID: 0006_add_all_day_timeslot
Revises: 0005_users_telegram_id_bigint
Create Date: 2026-04-11
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0006_add_all_day_timeslot"
down_revision = "0005_users_telegram_id_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE time_slot ADD VALUE IF NOT EXISTS 'all_day'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum value without type recreation.
    pass
