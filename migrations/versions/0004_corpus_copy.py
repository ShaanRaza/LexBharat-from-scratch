"""Corpus copy for fast reading: cases, act_sections, court_coverage.

Loaded from parquet by data/ scripts (not by migrations). Deliberately NO columns for
judges, petitioner or respondent: those fields failed the audit and must never be
displayed (CLAUDE.md section 6, docs/DATASET.md).
Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from lb_migration_helpers import create_table, drop_table, id_col, one_of

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table(
        "cases",
        id_col(),
        # record_id is the dataset's own ID (the same value stored in Qdrant).
        sa.Column("record_id", sa.Text, nullable=False, unique=True),
        sa.Column("title", sa.Text),
        sa.Column("court", sa.Text, nullable=False),
        sa.Column("decision_date", sa.Date),
        sa.Column("case_number", sa.Text),
        # Shown exactly as recorded; never retyped by the AI.
        sa.Column("citation", sa.Text),
        sa.Column("disposition", sa.Text),  # raw text from the dataset
        sa.Column("outcome_label", sa.Text),
        sa.Column("is_final_outcome", sa.Boolean),
        # True only for rows in the 50-judgment hand-check sample.
        sa.Column("outcome_checked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("pdf_url", sa.Text),
        sa.Column("full_text", sa.Text),
        sa.CheckConstraint(
            "outcome_label IS NULL OR outcome_label IN "
            "('allowed', 'partly allowed', 'dismissed', 'disposed of', 'other')",
            name="ck_cases_outcome_label",
        ),
        # /stats counts by court, year and outcome label.
        sa.Index("ix_cases_court_date", "court", "decision_date"),
        sa.Index("ix_cases_outcome_label", "outcome_label"),
        sa.Index("ix_cases_case_number", "case_number"),
    )

    create_table(
        "act_sections",
        id_col(),
        sa.Column("record_id", sa.Text, nullable=False, unique=True),
        sa.Column("act_name", sa.Text, nullable=False),
        sa.Column("act_year", sa.Integer),
        sa.Column("section_number", sa.Text, nullable=False),
        sa.Column("section_title", sa.Text),
        sa.Column("text", sa.Text),
        sa.Column("in_force", sa.Boolean),
        # Filled for only 1,568 of 22,264 acts. NULL => "in-force status not checked".
        sa.Column("act_status", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Index("ix_act_sections_lookup", sa.text("lower(act_name)"), "section_number"),
    )

    # The data-as-of date per court, shown on every result, stats page and Act page.
    create_table(
        "court_coverage",
        id_col(),
        sa.Column("court", sa.Text, nullable=False),
        sa.Column("snapshot_version", sa.Text, nullable=False),
        sa.Column("data_as_of", sa.Date, nullable=False),
        sa.Column("points", sa.BigInteger),
        sa.Column("live", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("stats_live", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("court", "snapshot_version", name="uq_court_coverage_key"),
    )


def downgrade() -> None:
    for name in ("court_coverage", "act_sections", "cases"):
        drop_table(name)
