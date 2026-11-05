"""audit_log: one row per login / upload / delete / export / admin view.
NEVER holds document text.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations._helpers import fk, id_col, stamps

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        id_col(),
        fk("user_id", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text),
        sa.Column("ip", postgresql.INET),
        sa.Column("request_id", sa.Text),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        *stamps(),
        sa.CheckConstraint(
            "action IN ('login', 'upload', 'delete', 'export', 'admin view')",
            name="ck_audit_log_action",
        ),
    )
    op.create_index("ix_audit_log_user_at", "audit_log", ["user_id", "at"])


def downgrade() -> None:
    op.drop_table("audit_log")
