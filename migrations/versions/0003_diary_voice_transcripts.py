"""add diary voice and transcripts

Revision ID: 0003_diary_voice_transcripts
Revises: 0002_diary_entries
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_diary_voice_transcripts"
down_revision = "0002_diary_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diary_voice",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("diary_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_file_id", sa.String(length=256), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(length=256), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("mime", sa.String(length=128), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("entry_id", name="uq_diary_voice_entry_id"),
    )
    op.create_index("ix_diary_voice_entry_id", "diary_voice", ["entry_id"], unique=True)
    op.create_index("ix_diary_voice_telegram_file_id", "diary_voice", ["telegram_file_id"], unique=False)
    op.create_index(
        "ix_diary_voice_telegram_file_unique_id",
        "diary_voice",
        ["telegram_file_unique_id"],
        unique=False,
    )

    op.create_table(
        "diary_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("diary_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("stt_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entry_id", name="uq_diary_transcripts_entry_id"),
    )
    op.create_index("ix_diary_transcripts_entry_id", "diary_transcripts", ["entry_id"], unique=True)
    op.create_index("ix_diary_transcripts_stt_status", "diary_transcripts", ["stt_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_diary_transcripts_stt_status", table_name="diary_transcripts")
    op.drop_index("ix_diary_transcripts_entry_id", table_name="diary_transcripts")
    op.drop_table("diary_transcripts")

    op.drop_index("ix_diary_voice_telegram_file_unique_id", table_name="diary_voice")
    op.drop_index("ix_diary_voice_telegram_file_id", table_name="diary_voice")
    op.drop_index("ix_diary_voice_entry_id", table_name="diary_voice")
    op.drop_table("diary_voice")
