"""add sport progression toggle and adherence flag

Revision ID: 0009_sport_progress_toggle
Revises: 0008_sport_progress
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_sport_progress_toggle"
down_revision = "0008_sport_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "habits",
        sa.Column(
            "sport_progression_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column("habit_checkins", sa.Column("sport_plan_adhered", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("habit_checkins", "sport_plan_adhered")
    op.drop_column("habits", "sport_progression_enabled")
