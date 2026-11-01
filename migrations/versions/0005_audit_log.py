"""Records: audit_log.

audit_log NEVER stores document text. user_id is SET NULL on account deletion so the
"who did what" trail survives without keeping the person (retention: Needs counsel).
Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from lb_migration_helpers import create_table, drop_table, fk, id_col, one_of

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table(
        "audit_log",
        id_col(),
        fk("user_id", "users.id", ondelete="SET NULL", nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text),
        sa.Column("ip", sa.Text),
        sa.Column("request_id", sa.Text),
        sa.Column(
            "at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        one_of(
            "action",
            ["login", "upload", "delete", "export", "admin_view"],
            "ck_audit_log_action",
        ),
        sa.Index("ix_audit_log_user_at", "user_id", "at"),
        sa.Index("ix_audit_log_request_id", "request_id"),
    )


def downgrade() -> None:
    drop_table("audit_log")
