"""add search indexes for diary and transcripts

Revision ID: 0004_diary_search_indexes
Revises: 0003_diary_voice_transcripts
Create Date: 2026-04-11
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0004_diary_search_indexes"
down_revision = "0003_diary_voice_transcripts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_diary_entries_text_trgm "
        "ON diary_entries USING gin (text_body gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_diary_transcripts_text_trgm "
        "ON diary_transcripts USING gin (transcript_text gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_diary_entries_text_fts "
        "ON diary_entries USING gin (to_tsvector('russian', coalesce(text_body, '')))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_diary_transcripts_text_fts "
        "ON diary_transcripts USING gin (to_tsvector('russian', coalesce(transcript_text, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_diary_transcripts_text_fts")
    op.execute("DROP INDEX IF EXISTS ix_diary_entries_text_fts")
    op.execute("DROP INDEX IF EXISTS ix_diary_transcripts_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_diary_entries_text_trgm")
