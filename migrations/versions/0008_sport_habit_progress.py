"""add sport progression fields to habits and checkins

Revision ID: 0008_sport_progress
Revises: 0007_habit_icon_weekly
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_sport_progress"
down_revision = "0007_habit_icon_weekly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("habits", sa.Column("is_sport", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("habits", sa.Column("sport_base_sets", sa.Integer(), nullable=True))
    op.add_column("habits", sa.Column("sport_base_reps", sa.Integer(), nullable=True))
    op.add_column("habits", sa.Column("sport_linear_step_reps", sa.Integer(), nullable=True))
    op.add_column("habits", sa.Column("sport_start_date", sa.Date(), nullable=True))

    op.add_column("habit_checkins", sa.Column("actual_sets", sa.Integer(), nullable=True))
    op.add_column("habit_checkins", sa.Column("actual_reps_csv", sa.String(length=256), nullable=True))
    op.add_column("habit_checkins", sa.Column("target_sets", sa.Integer(), nullable=True))
    op.add_column("habit_checkins", sa.Column("target_reps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("habit_checkins", "target_reps")
    op.drop_column("habit_checkins", "target_sets")
    op.drop_column("habit_checkins", "actual_reps_csv")
    op.drop_column("habit_checkins", "actual_sets")

    op.drop_column("habits", "sport_start_date")
    op.drop_column("habits", "sport_linear_step_reps")
    op.drop_column("habits", "sport_base_reps")
    op.drop_column("habits", "sport_base_sets")
    op.drop_column("habits", "is_sport")
