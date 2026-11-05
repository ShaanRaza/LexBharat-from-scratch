"""share_links: share one stored answer by an unguessable, revocable, expiring link.

Plain words (PRD-v2 O14): only an answer built purely from the public dataset may be
shared. The provenance flags written when the answer was saved (A47) say whether an
upload or a remembered matter fact shaped it. This migration makes that rule hold even
if application code forgets it: a database trigger refuses to create a link for a
message that is not an assistant answer of the same user, or that is shaped by an upload
or a matter fact.

The token itself is NEVER stored, only its SHA-256 (token_hash). Revoking sets
revoked_at; the public route checks the row on every request, never a cache.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import fk, id_col, stamps

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        fk("message_id", "messages.id", ondelete="CASCADE"),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *stamps(),
        sa.UniqueConstraint("token_hash", name="uq_share_links_token_hash"),
    )
    op.create_index("ix_share_links_user", "share_links", ["user_id", "created_at"])
    op.execute(
        """
        CREATE FUNCTION share_links_guard() RETURNS trigger AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM messages m
              JOIN conversations c ON c.id = m.conversation_id
             WHERE m.id = NEW.message_id
               AND c.user_id = NEW.user_id
               AND m.role = 'assistant'
               AND NOT m.shaped_by_upload
               AND NOT m.shaped_by_matter_fact
          ) THEN
            RAISE EXCEPTION 'this answer cannot be shared'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER share_links_guard BEFORE INSERT ON share_links "
        "FOR EACH ROW EXECUTE FUNCTION share_links_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER share_links_guard ON share_links")
    op.execute("DROP FUNCTION share_links_guard()")
    op.drop_index("ix_share_links_user", table_name="share_links")
    op.drop_table("share_links")
