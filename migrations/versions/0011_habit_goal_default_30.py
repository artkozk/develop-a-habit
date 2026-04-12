"""set default 30-day goals and backfill existing habits

Revision ID: 0011_habit_goal_default_30
Revises: 0010_habit_goal_cycles
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_habit_goal_default_30"
down_revision = "0010_habit_goal_cycles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE habits
        SET goal_days = 30
        WHERE goal_days IS NULL OR goal_days <= 0
        """
    )
    op.execute(
        """
        UPDATE habits
        SET goal_start_date = COALESCE(goal_start_date, DATE(created_at), CURRENT_DATE)
        WHERE goal_days IS NOT NULL
        """
    )
    op.alter_column(
        "habits",
        "goal_days",
        existing_type=sa.Integer(),
        server_default=sa.text("30"),
    )


def downgrade() -> None:
    op.alter_column(
        "habits",
        "goal_days",
        existing_type=sa.Integer(),
        server_default=None,
    )
