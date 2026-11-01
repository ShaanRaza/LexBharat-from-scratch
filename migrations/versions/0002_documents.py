"""Uploads: documents and document_chunks.

page_no, char_start and char_end let a citation jump to and highlight the exact
passage in the viewer. Do not drop them (docs/DATA-MODEL.md).
Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from lb_migration_helpers import create_table, drop_table, fk, id_col, one_of

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_table(
        "documents",
        id_col(),
        fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("page_count", sa.Integer),
        sa.Column("status", sa.Text, nullable=False, server_default="uploaded"),
        sa.Column("fail_reason", sa.Text),
        sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("storage_path", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        one_of(
            "status",
            ["uploaded", "extracting", "indexing", "ready", "failed"],
            "ck_documents_status",
        ),
        sa.Index("ix_documents_user_id", "user_id"),
        # The nightly "leftover check" and the expiry job scan by expires_at.
        sa.Index("ix_documents_expires_at", "expires_at"),
    )

    create_table(
        "document_chunks",
        id_col(),
        fk("document_id", "documents.id", ondelete="CASCADE"),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        # Point ID in the Qdrant `user_documents` collection.
        sa.Column("vector_id", sa.Text),
        sa.CheckConstraint("char_end >= char_start", name="ck_chunks_offsets"),
        sa.Index("ix_document_chunks_document_id", "document_id", "page_no"),
    )


def downgrade() -> None:
    drop_table("document_chunks")
    drop_table("documents")
