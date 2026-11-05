"""matters + nullable matter_id on user-work tables + answer provenance flags.

Plain words: a matter is one case or project that saved work hangs off (PRD-v2 O11).
One table; "Matter" vs "Project" is the `kind` label, not a second feature.

Two schema rules from TECH-STACK-v2 section 6, applied here because they are cheap now
and expensive to retrofit:
  1. every table holding user work carries a NULLABLE matter_id (existing ones:
     conversations, messages, documents; saved items, notes, drafts and exports do not
     exist yet and must carry it from THEIR first migration);
  2. every stored answer records whether an upload or a remembered matter fact shaped
     it (shaped_by_upload, shaped_by_matter_fact). They are written when the answer is
     saved. The default is dropped after the backfill, so a save that forgets to set
     them fails instead of silently saying "no".

Deleting a matter sets matter_id to NULL on its work (the work is kept). What happens
to matter facts on deletion is O13 and no memory table exists yet.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import UUID, check_in, fk, id_col, stamps

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Tables that already hold user work and so get a nullable matter_id now.
USER_WORK = ("conversations", "messages", "documents")


def upgrade() -> None:
    op.create_table(
        "matters",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False, server_default="matter"),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *stamps(),
        check_in("kind", ["matter", "project"], "ck_matters_kind"),
        check_in("status", ["active", "archived"], "ck_matters_status"),
        sa.CheckConstraint(
            "(status = 'archived') = (archived_at IS NOT NULL)",
            name="ck_matters_archived_at",
        ),
    )
    op.create_index("ix_matters_user", "matters", ["user_id", "status"])
    for table in USER_WORK:
        op.add_column(
            table,
            sa.Column(
                "matter_id",
                UUID,
                sa.ForeignKey("matters.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_matter", table, ["matter_id"])
    for col in ("shaped_by_upload", "shaped_by_matter_fact"):
        op.add_column(
            "messages",
            sa.Column(col, sa.Boolean, nullable=False, server_default=sa.false()),
        )
        # Old rows are backfilled with false (uploads were switched off), then the
        # default goes so every new row must say it explicitly.
        op.alter_column("messages", col, server_default=None)


def downgrade() -> None:
    for col in ("shaped_by_matter_fact", "shaped_by_upload"):
        op.drop_column("messages", col)
    for table in reversed(USER_WORK):
        op.drop_index(f"ix_{table}_matter", table_name=table)
        op.drop_column(table, "matter_id")
    op.drop_index("ix_matters_user", table_name="matters")
    op.drop_table("matters")
