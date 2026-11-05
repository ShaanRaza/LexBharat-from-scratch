"""uploads: documents, document_chunks. page_no / char_start / char_end are what
let a citation jump to and highlight the exact passage. Do not drop them.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

from migrations._helpers import check_in, fk, id_col, stamps

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("status", sa.Text, nullable=False, server_default="uploaded"),
        sa.Column("fail_reason", sa.Text),
        sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("storage_path", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *stamps(),
        check_in(
            "status",
            ["uploaded", "extracting", "indexing", "ready", "failed"],
            "ck_documents_status",
        ),
    )
    op.create_index("ix_documents_user", "documents", ["user_id"])
    op.create_table(
        "document_chunks",
        id_col(),
        fk("document_id", "documents.id", ondelete="CASCADE"),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("vector_id", sa.Text),
        *stamps(),
    )
    op.create_index("ix_document_chunks_document", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
