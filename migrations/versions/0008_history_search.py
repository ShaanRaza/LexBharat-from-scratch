"""Full-text indexes so a user can search their own conversations and answers.

Plain words: history search is PostgreSQL full text (no new vendor). The two indexes
match the exact expressions the search query uses, so it stays fast. Every search is
still filtered by user_id in the query (core/user_search.py); an index never decides
who may see a row.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_messages_content_fts ON messages "
        "USING gin (to_tsvector('english', content))"
    )
    op.execute(
        "CREATE INDEX ix_conversations_title_fts ON conversations "
        "USING gin (to_tsvector('english', COALESCE(title, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_conversations_title_fts")
    op.execute("DROP INDEX ix_messages_content_fts")
