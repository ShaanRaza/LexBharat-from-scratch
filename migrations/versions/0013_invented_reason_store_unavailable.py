"""invented_citation_log.reason: a fifth value, 'store unavailable'.

Plain words: check 2 of the verifier asks the record store whether a cited record
exists. When the store could not be asked (a timeout or an outage) the citation is still
removed (fail closed), but it used to be logged as 'record missing', which reads as the
model inventing a citation and corrupts the invented-citation metric. It now logs
'store unavailable'. The metric counts only the other four reasons.

The check constraint allowed exactly four values, so it is replaced with one that
allows five. The downgrade maps the new value back to 'record missing' (the old
behaviour) before restoring the four-value constraint, so it cannot fail on rows.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

from migrations._helpers import check_in

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

NAME = "ck_invented_citation_reason"
OLD = ["not retrieved", "record missing", "quote not found", "claim not supported"]
NEW = [*OLD, "store unavailable"]


def _swap(values: list[str]) -> None:
    op.drop_constraint(NAME, "invented_citation_log", type_="check")
    c = check_in("reason", values, NAME)
    op.create_check_constraint(NAME, "invented_citation_log", c.sqltext)


def upgrade() -> None:
    _swap(NEW)


def downgrade() -> None:
    op.execute(
        "UPDATE invented_citation_log SET reason = 'record missing' "
        "WHERE reason = 'store unavailable'"
    )
    _swap(OLD)
