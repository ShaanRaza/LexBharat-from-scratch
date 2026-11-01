"""conversations and trust: conversations, messages, message_sources,
invented_citation_log, feedback. invented_citation_log is the trust metric's source.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import check_in, fk, id_col, stamps

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("module", sa.Text, nullable=False, server_default="research"),
        fk("document_id", "documents.id", nullable=True, ondelete="SET NULL"),
        sa.Column("title", sa.Text),
        sa.Column("rolling_summary", sa.Text),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        *stamps(),
        check_in("module", ["research", "document"], "ck_conversations_module"),
    )
    op.create_index("ix_conversations_user", "conversations", ["user_id", "created_at"])
    op.create_table(
        "messages",
        id_col(),
        fk("conversation_id", "conversations.id", ondelete="CASCADE"),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("rewritten_query", sa.Text),
        sa.Column("model", sa.Text),
        sa.Column("tokens_in", sa.Integer),
        sa.Column("tokens_out", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("from_cache", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("scope", sa.Text),
        sa.Column("route", sa.Text),
        sa.Column("safety", sa.Text),
        sa.Column("jev_used", sa.Boolean, nullable=False, server_default=sa.false()),
        *stamps(),
        check_in("role", ["user", "assistant"], "ck_messages_role"),
        sa.CheckConstraint(
            "route IS NULL OR route IN ('easy', 'hard')", name="ck_messages_route"
        ),
    )
    op.create_index(
        "ix_messages_conversation", "messages", ["conversation_id", "created_at"]
    )
    op.create_table(
        "message_sources",
        fk("message_id", "messages.id", ondelete="CASCADE"),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("record_id", sa.Text, nullable=False),
        sa.Column("chunk_id", sa.Text),
        sa.Column("rank", sa.Integer),
        sa.Column("rerank_score", sa.Float),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("relevance", sa.Text),
        sa.Column("support", sa.Text),
        sa.Column("support_confidence", sa.Float),
        *stamps(),
        sa.PrimaryKeyConstraint("message_id", "source_id"),
        sa.CheckConstraint("source_id ~ '^S[1-8]$'", name="ck_message_sources_label"),
        sa.CheckConstraint(
            "support IS NULL OR support IN ('supports', 'partly', 'does not')",
            name="ck_message_sources_support",
        ),
    )
    op.create_table(
        "invented_citation_log",
        id_col(),
        fk("message_id", "messages.id", nullable=True, ondelete="SET NULL"),
        sa.Column("query", sa.Text),
        sa.Column("model", sa.Text),
        sa.Column("cited_text", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        *stamps(),
        check_in(
            "reason",
            [
                "not retrieved",
                "record missing",
                "quote not found",
                "claim not supported",
            ],
            "ck_invented_citation_reason",
        ),
    )
    op.create_table(
        "feedback",
        id_col(),
        fk("message_id", "messages.id", ondelete="CASCADE"),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("rating", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("comment", sa.Text),
        *stamps(),
        check_in("rating", ["up", "down"], "ck_feedback_rating"),
    )


def downgrade() -> None:
    for t in [
        "feedback",
        "invented_citation_log",
        "message_sources",
        "messages",
        "conversations",
    ]:
        op.drop_table(t)
