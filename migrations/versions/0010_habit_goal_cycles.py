"""add habit goal and cycle tracking fields

Revision ID: 0010_habit_goal_cycles
Revises: 0009_sport_progress_toggle
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_habit_goal_cycles"
down_revision = "0009_sport_progress_toggle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("habits", sa.Column("goal_days", sa.Integer(), nullable=True))
    op.add_column("habits", sa.Column("goal_start_date", sa.Date(), nullable=True))
    op.add_column(
        "habits",
        sa.Column("goal_completed_cycles", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("habits", "goal_completed_cycles")
    op.drop_column("habits", "goal_start_date")
    op.drop_column("habits", "goal_days")
