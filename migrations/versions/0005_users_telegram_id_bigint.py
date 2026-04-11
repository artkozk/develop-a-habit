"""widen telegram user id to bigint

Revision ID: 0005_users_telegram_id_bigint
Revises: 0004_diary_search_indexes
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_users_telegram_id_bigint"
down_revision = "0004_diary_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "telegram_user_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "telegram_user_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
