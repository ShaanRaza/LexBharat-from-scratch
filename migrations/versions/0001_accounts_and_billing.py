"""Accounts and billing: users, organisations, subscriptions, memberships, usage_daily, consents.

Also creates the set_updated_at() trigger function used by every table.
Revision ID: 0001
Revises: (none)
"""

import sqlalchemy as sa
from alembic import op
from lb_migration_helpers import create_table, drop_table, fk, id_col, one_of

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One function, reused by a trigger on every table: stamps updated_at on UPDATE.
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # No password column: Firebase holds passwords; we keep only its user ID.
    create_table(
        "users",
        id_col(),
        sa.Column("firebase_uid", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("role", sa.Text, nullable=False, server_default="other"),
        sa.Column("plan", sa.Text, nullable=False, server_default="free"),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        one_of("role", ["advocate", "student", "in-house", "other"], "ck_users_role"),
        one_of("plan", ["free", "student", "pro", "chambers"], "ck_users_plan"),
        one_of("status", ["active", "suspended", "deleted"], "ck_users_status"),
    )

    # RESTRICT: an owner cannot vanish and orphan a paying organisation.
    # DELETE /me must tell the owner to transfer or close the organisation first.
    create_table(
        "organisations",
        id_col(),
        sa.Column("name", sa.Text, nullable=False),
        fk("owner_user_id", "users.id", ondelete="RESTRICT"),
        sa.Column("plan", sa.Text, nullable=False, server_default="chambers"),
        sa.Column("seats", sa.Integer, nullable=False, server_default="3"),
        # Chambers = minimum 3 seats, one bill (docs/DATA-MODEL.md).
        sa.CheckConstraint("seats >= 3", name="ck_organisations_min_seats"),
    )

    # SET NULL (not CASCADE): payment records must survive DELETE /me because the
    # law requires it. The retention period is "Needs counsel" (docs/RETENTION.md).
    create_table(
        "subscriptions",
        id_col(),
        fk("user_id", "users.id", ondelete="SET NULL", nullable=True),
        fk("organisation_id", "organisations.id", ondelete="SET NULL", nullable=True),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("seats", sa.Integer, nullable=False, server_default="1"),
        sa.Column("razorpay_subscription_id", sa.Text, unique=True),
        sa.Column("status", sa.Text, nullable=False, server_default="created"),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        one_of("plan", ["free", "student", "pro", "chambers"], "ck_subscriptions_plan"),
        # Razorpay's own subscription statuses.
        one_of(
            "status",
            [
                "created",
                "authenticated",
                "active",
                "pending",
                "halted",
                "cancelled",
                "completed",
                "expired",
                "paused",
            ],
            "ck_subscriptions_status",
        ),
        sa.Index("ix_subscriptions_user_id", "user_id"),
        sa.Index("ix_subscriptions_organisation_id", "organisation_id"),
    )

    create_table(
        "memberships",
        id_col(),
        fk("organisation_id", "organisations.id", ondelete="CASCADE"),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("role", sa.Text, nullable=False, server_default="member"),
        sa.Column("status", sa.Text, nullable=False, server_default="invited"),
        one_of("role", ["admin", "member"], "ck_memberships_role"),
        one_of("status", ["invited", "active", "removed"], "ck_memberships_status"),
        sa.UniqueConstraint(
            "organisation_id", "user_id", name="uq_memberships_org_user"
        ),
        sa.Index("ix_memberships_user_id", "user_id"),
    )

    # One row per user per day per feature: the usage meter's source of truth.
    create_table(
        "usage_daily",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("feature", sa.Text, nullable=False),
        sa.Column("requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "cost_estimate", sa.Numeric(12, 6), nullable=False, server_default="0"
        ),
        sa.UniqueConstraint("user_id", "date", "feature", name="uq_usage_daily_key"),
    )

    # notice_version points at a versioned document in legal/ (DPDP consent).
    create_table(
        "consents",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("notice_version", sa.Text, nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("given_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Index("ix_consents_user_id", "user_id"),
    )


def downgrade() -> None:
    for name in (
        "consents",
        "usage_daily",
        "memberships",
        "subscriptions",
        "organisations",
        "users",
    ):
        drop_table(name)
    op.execute("DROP FUNCTION set_updated_at()")
