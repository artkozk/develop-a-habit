"""create base habit tables

Revision ID: 0001_base_habits
Revises:
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_base_habits"
down_revision = None
branch_labels = None
depends_on = None


habit_type = postgresql.ENUM("positive", "negative", name="habit_type", create_type=False)
time_slot = postgresql.ENUM("morning", "day", "evening", name="time_slot", create_type=False)
schedule_type = postgresql.ENUM(
    "daily",
    "every_other_day",
    "specific_weekdays",
    name="schedule_type",
    create_type=False,
)
checkin_status = postgresql.ENUM(
    "done",
    "missed",
    "violated",
    "optional_done",
    name="checkin_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    habit_type.create(bind, checkfirst=True)
    time_slot.create(bind, checkfirst=True)
    schedule_type.create(bind, checkfirst=True)
    checkin_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=128), nullable=False, server_default="Europe/Moscow"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)

    op.create_table(
        "habits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("habit_type", habit_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_habits_user_id", "habits", ["user_id"], unique=False)

    op.create_table(
        "habit_schedule_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("habit_id", sa.Integer(), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_type", schedule_type, nullable=False),
        sa.Column("time_slot", time_slot, nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_from", sa.Date(), nullable=True),
    )
    op.create_index("ix_habit_schedule_rules_habit_id", "habit_schedule_rules", ["habit_id"], unique=False)
    op.create_index("ix_habit_schedule_rules_time_slot", "habit_schedule_rules", ["time_slot"], unique=False)

    op.create_table(
        "day_off_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("exact_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_day_off_rules_user_id", "day_off_rules", ["user_id"], unique=False)

    op.create_table(
        "habit_checkins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("habit_id", sa.Integer(), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("time_slot", time_slot, nullable=False),
        sa.Column("status", checkin_status, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("habit_id", "check_date", "time_slot", name="uq_habit_checkin_slot"),
    )
    op.create_index("ix_habit_checkins_habit_id", "habit_checkins", ["habit_id"], unique=False)
    op.create_index("ix_habit_checkins_check_date", "habit_checkins", ["check_date"], unique=False)
    op.create_index("ix_habit_checkins_time_slot", "habit_checkins", ["time_slot"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_habit_checkins_time_slot", table_name="habit_checkins")
    op.drop_index("ix_habit_checkins_check_date", table_name="habit_checkins")
    op.drop_index("ix_habit_checkins_habit_id", table_name="habit_checkins")
    op.drop_table("habit_checkins")

    op.drop_index("ix_day_off_rules_user_id", table_name="day_off_rules")
    op.drop_table("day_off_rules")

    op.drop_index("ix_habit_schedule_rules_time_slot", table_name="habit_schedule_rules")
    op.drop_index("ix_habit_schedule_rules_habit_id", table_name="habit_schedule_rules")
    op.drop_table("habit_schedule_rules")

    op.drop_index("ix_habits_user_id", table_name="habits")
    op.drop_table("habits")

    op.drop_index("ix_users_telegram_user_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    checkin_status.drop(bind, checkfirst=True)
    schedule_type.drop(bind, checkfirst=True)
    time_slot.drop(bind, checkfirst=True)
    habit_type.drop(bind, checkfirst=True)
