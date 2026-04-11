"""add habit icon emoji and weekly prompts table

Revision ID: 0007_habit_icon_and_weekly_prompts
Revises: 0006_add_all_day_timeslot
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_habit_icon_and_weekly_prompts"
down_revision = "0006_add_all_day_timeslot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("habits", sa.Column("icon_emoji", sa.String(length=16), nullable=True))

    op.create_table(
        "weekly_prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("comment_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_prompt_user_week"),
    )
    op.create_index("ix_weekly_prompts_user_id", "weekly_prompts", ["user_id"], unique=False)
    op.create_index("ix_weekly_prompts_week_start", "weekly_prompts", ["week_start"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_weekly_prompts_week_start", table_name="weekly_prompts")
    op.drop_index("ix_weekly_prompts_user_id", table_name="weekly_prompts")
    op.drop_table("weekly_prompts")
    op.drop_column("habits", "icon_emoji")
