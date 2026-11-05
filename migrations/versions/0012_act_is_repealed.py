"""act_sections.is_repealed: the dataset's own repealed flag, as a fourth repeal signal.

Plain words (A181): an Act reads "repealed" if act_status, an IND_REP_ id, a clean
(Rep., Act NN of YYYY) title marker, or this flag says so (core/act_status.py).
Repealed is the safe direction, so every extra signal only protects the reader. The
column is nullable and has no default: unloaded rows are "unknown", never "not
repealed". It never makes anything read "in force".

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("act_sections", sa.Column("is_repealed", sa.Boolean, nullable=True))


def downgrade() -> None:
    op.drop_column("act_sections", "is_repealed")
