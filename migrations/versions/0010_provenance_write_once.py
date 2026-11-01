"""Provenance flags become write-once; the share-link guard also fires on UPDATE.

Plain words (A47, A56, A59): the two flags on a stored answer (`shaped_by_upload`,
`shaped_by_matter_fact`) are written once, when the answer is saved. The adversarial
trust tests showed two ways round that in the database itself:

  1. `UPDATE messages SET shaped_by_upload = false` on a shaped answer cleared the
     flag, after which sharing it was allowed. A trigger now refuses ever clearing a
     flag that is true. (Setting a flag to true later is allowed: that only makes an
     answer less shareable.)
  2. The share-link guard ran only on INSERT, so `UPDATE share_links SET message_id =
     ...` could point a link at a shaped answer. The guard now also runs on UPDATE of
     message_id or user_id. (Revoking a link updates only revoked_at, so it is never
     blocked.)

The flag columns are NOT NULL with no default (0006), so an unknown provenance cannot be
stored at all.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION messages_provenance_write_once() RETURNS trigger AS $$
        BEGIN
          IF (OLD.shaped_by_upload AND NOT NEW.shaped_by_upload)
             OR (OLD.shaped_by_matter_fact AND NOT NEW.shaped_by_matter_fact) THEN
            RAISE EXCEPTION 'provenance flags cannot be cleared once set'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER messages_provenance_write_once "
        "BEFORE UPDATE OF shaped_by_upload, shaped_by_matter_fact ON messages "
        "FOR EACH ROW EXECUTE FUNCTION messages_provenance_write_once()"
    )
    op.execute("DROP TRIGGER share_links_guard ON share_links")
    op.execute(
        "CREATE TRIGGER share_links_guard "
        "BEFORE INSERT OR UPDATE OF message_id, user_id ON share_links "
        "FOR EACH ROW EXECUTE FUNCTION share_links_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER share_links_guard ON share_links")
    op.execute(
        "CREATE TRIGGER share_links_guard BEFORE INSERT ON share_links "
        "FOR EACH ROW EXECUTE FUNCTION share_links_guard()"
    )
    op.execute("DROP TRIGGER messages_provenance_write_once ON messages")
    op.execute("DROP FUNCTION messages_provenance_write_once()")
