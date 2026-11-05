"""corpus copy for fast reading: cases, act_sections, court_coverage.
Loaded from parquet by data/ scripts. No judges or party columns on purpose:
those fields are unreliable and must never be displayed.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import stamps

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("record_id", sa.Text, primary_key=True),
        sa.Column("title", sa.Text),
        sa.Column("court", sa.Text),
        sa.Column("decision_date", sa.Date),
        sa.Column("case_number", sa.Text),
        sa.Column("citation", sa.Text),
        sa.Column("disposition", sa.Text),
        sa.Column("outcome_label", sa.Text),
        sa.Column("is_final_outcome", sa.Boolean),
        sa.Column(
            "outcome_checked", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("pdf_url", sa.Text),
        sa.Column("full_text", sa.Text),
        *stamps(),
        sa.CheckConstraint(
            "outcome_label IS NULL OR outcome_label IN "
            "('allowed', 'partly allowed', 'dismissed', 'disposed of', 'other')",
            name="ck_cases_outcome_label",
        ),
    )
    op.create_index("ix_cases_court_date", "cases", ["court", "decision_date"])
    op.create_index("ix_cases_case_number", "cases", ["case_number"])
    op.create_table(
        "act_sections",
        sa.Column("record_id", sa.Text, primary_key=True),
        sa.Column("act_name", sa.Text, nullable=False),
        sa.Column("act_year", sa.Integer),
        sa.Column("section_number", sa.Text),
        sa.Column("section_title", sa.Text),
        sa.Column("text", sa.Text),
        sa.Column("in_force", sa.Boolean),
        sa.Column("act_status", sa.Text),
        sa.Column("source_url", sa.Text),
        *stamps(),
    )
    op.create_index(
        "ix_act_sections_lookup",
        "act_sections",
        ["act_name", "act_year", "section_number"],
    )
    op.create_table(
        "court_coverage",
        sa.Column("court", sa.Text, primary_key=True),
        sa.Column("snapshot_version", sa.Text, nullable=False),
        sa.Column("data_as_of", sa.Date, nullable=False),
        sa.Column("points", sa.BigInteger),
        sa.Column("live", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("stats_live", sa.Boolean, nullable=False, server_default=sa.false()),
        *stamps(),
    )


def downgrade() -> None:
    for t in ["court_coverage", "act_sections", "cases"]:
        op.drop_table(t)
