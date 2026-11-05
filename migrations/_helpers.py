"""Small helpers shared by migrations (kept out of versions/ so alembic skips them)."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

UUID = postgresql.UUID(as_uuid=True)


def id_col() -> sa.Column:
    return sa.Column(
        "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def fk(name: str, target: str, nullable: bool = False, ondelete: str | None = None):
    return sa.Column(
        name, UUID, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable
    )


def stamps() -> list[sa.Column]:
    """created_at / updated_at on every table (docs/DATA-MODEL.md conventions)."""
    now = sa.text("now()")
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=now, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False
        ),
    ]


def check_in(column: str, values: list[str], name: str) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{v}'" for v in values)
    return sa.CheckConstraint(f"{column} IN ({quoted})", name=name)
