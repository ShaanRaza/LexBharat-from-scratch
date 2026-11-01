"""accounts and billing: users, organisations, memberships, subscriptions,
usage_daily, consents. No password column anywhere: Firebase holds passwords.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import check_in, fk, id_col, stamps

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        id_col(),
        sa.Column("firebase_uid", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text),
        sa.Column("name", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("plan", sa.Text, nullable=False, server_default="free"),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        *stamps(),
        check_in("role", ["advocate", "student", "in-house", "other"], "ck_users_role"),
    )
    op.create_table(
        "organisations",
        id_col(),
        sa.Column("name", sa.Text, nullable=False),
        fk("owner_user_id", "users.id"),
        sa.Column("plan", sa.Text, nullable=False, server_default="chambers"),
        sa.Column("seats", sa.Integer, nullable=False),
        *stamps(),
        sa.CheckConstraint("seats >= 3", name="ck_organisations_min_seats"),
    )
    op.create_table(
        "memberships",
        id_col(),
        fk("organisation_id", "organisations.id", ondelete="CASCADE"),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("role", sa.Text, nullable=False, server_default="member"),
        sa.Column("status", sa.Text, nullable=False, server_default="invited"),
        *stamps(),
        sa.UniqueConstraint(
            "organisation_id", "user_id", name="uq_memberships_org_user"
        ),
        check_in("role", ["admin", "member"], "ck_memberships_role"),
        check_in("status", ["invited", "active", "removed"], "ck_memberships_status"),
    )
    op.create_table(
        "subscriptions",
        id_col(),
        fk("user_id", "users.id", nullable=True),
        fk("organisation_id", "organisations.id", nullable=True),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("seats", sa.Integer),
        sa.Column("razorpay_subscription_id", sa.Text, unique=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        *stamps(),
        sa.CheckConstraint(
            "(user_id IS NOT NULL) <> (organisation_id IS NOT NULL)",
            name="ck_subscriptions_one_owner",
        ),
    )
    op.create_table(
        "usage_daily",
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("feature", sa.Text, nullable=False),
        sa.Column("requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "cost_estimate", sa.Numeric(12, 6), nullable=False, server_default="0"
        ),
        *stamps(),
        sa.PrimaryKeyConstraint("user_id", "date", "feature"),
    )
    op.create_table(
        "consents",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("notice_version", sa.Text, nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column(
            "given_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        *stamps(),
    )
    op.create_index("ix_consents_user", "consents", ["user_id"])


def downgrade() -> None:
    for t in [
        "consents",
        "usage_daily",
        "subscriptions",
        "memberships",
        "organisations",
        "users",
    ]:
        op.drop_table(t)
