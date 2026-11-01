"""Conversations and trust: conversations, messages, message_sources,
invented_citation_log, feedback.

invented_citation_log is the source of the trust metric (target: under 0.5% of
answers with a removed citation).
Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from lb_migration_helpers import create_table, drop_table, fk, id_col, one_of

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table(
        "conversations",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("module", sa.Text, nullable=False, server_default="research"),
        # If the upload is deleted the chat stays, but no longer points at it.
        fk("document_id", "documents.id", ondelete="SET NULL", nullable=True),
        sa.Column("title", sa.Text),
        sa.Column("rolling_summary", sa.Text),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        one_of("module", ["research", "document"], "ck_conversations_module"),
        # Powers cursor pagination: newest first, per user.
        sa.Index("ix_conversations_user_created", "user_id", "created_at", "id"),
    )

    create_table(
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
        one_of("role", ["user", "assistant"], "ck_messages_role"),
        sa.CheckConstraint(
            "route IS NULL OR route IN ('easy', 'hard')", name="ck_messages_route"
        ),
        sa.Index("ix_messages_conversation", "conversation_id", "created_at", "id"),
    )

    create_table(
        "message_sources",
        id_col(),
        fk("message_id", "messages.id", ondelete="CASCADE"),
        # S1..S8 are the labels the model was given this turn (CLAUDE.md step 7).
        sa.Column("source_id", sa.Text, nullable=False),
        # record_id points into kanoon_v1; no FK because it may be a case or an Act section.
        sa.Column("record_id", sa.Text, nullable=False),
        sa.Column("chunk_id", sa.Text),
        sa.Column("rank", sa.Integer),
        sa.Column("rerank_score", sa.Float),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("relevance", sa.Text),
        sa.Column("support", sa.Text),
        sa.Column("support_confidence", sa.Float),
        sa.CheckConstraint("source_id ~ '^S[1-8]$'", name="ck_message_sources_label"),
        one_of(
            "relevance",
            ["answers_it", "partly", "not_relevant"],
            "ck_message_sources_relevance",
        ),
        one_of(
            "support",
            ["supports", "partly", "does_not_support"],
            "ck_message_sources_support",
        ),
        sa.UniqueConstraint("message_id", "source_id", name="uq_message_sources_label"),
        sa.Index("ix_message_sources_record_id", "record_id"),
    )

    # CASCADE on purpose: query and cited_text come from the user, so they go when
    # the user's account is hard-deleted (privacy beats keeping the metric row).
    create_table(
        "invented_citation_log",
        id_col(),
        fk("message_id", "messages.id", ondelete="CASCADE"),
        sa.Column("query", sa.Text),
        sa.Column("model", sa.Text),
        sa.Column("cited_text", sa.Text),
        sa.Column("reason", sa.Text, nullable=False),
        one_of(
            "reason",
            ["not_retrieved", "record_missing", "quote_not_found", "claim_not_supported"],
            "ck_invented_citation_reason",
        ),
        sa.Index("ix_invented_citation_message_id", "message_id"),
    )

    create_table(
        "feedback",
        id_col(),
        fk("message_id", "messages.id", ondelete="CASCADE"),
        fk("user_id", "users.id", ondelete="CASCADE"),
        # Thumbs: 1 = up, -1 = down.
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("comment", sa.Text),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"),
    )


def downgrade() -> None:
    for name in (
        "feedback",
        "invented_citation_log",
        "message_sources",
        "messages",
        "conversations",
    ):
        drop_table(name)
