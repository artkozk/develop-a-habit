"""add diary text entries

Revision ID: 0002_diary_entries
Revises: 0001_base_habits
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0002_diary_entries"
down_revision = "0001_base_habits"
branch_labels = None
depends_on = None


diary_entry_type = postgresql.ENUM("text", "voice", "mixed", name="diary_entry_type", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    diary_entry_type.create(bind, checkfirst=True)

    op.create_table(
        "diary_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("entry_type", diary_entry_type, nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_diary_entries_user_id", "diary_entries", ["user_id"], unique=False)
    op.create_index("ix_diary_entries_entry_date", "diary_entries", ["entry_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_diary_entries_entry_date", table_name="diary_entries")
    op.drop_index("ix_diary_entries_user_id", table_name="diary_entries")
    op.drop_table("diary_entries")

    bind = op.get_bind()
    diary_entry_type.drop(bind, checkfirst=True)
