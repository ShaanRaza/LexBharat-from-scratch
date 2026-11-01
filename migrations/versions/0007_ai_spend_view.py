"""ai_spend_daily: one view of every paid model call we can count, per day.

Plain words: the "Improve my question" helper and the next-question suggestions call
Gemini but are not answers, so they record their tokens in usage_daily under their own
feature name (they never use the answer limit). This view puts those rows next to the
answers' own tokens (from messages, cache hits excluded) so the daily AI spend and the
cost per answer (PRD-v2 section 5.1) include them. No money is stored: it is worked out
when read, from the configured price, so a price change applies to history too.

Not counted anywhere yet (an existing gap, not new): tokens of the rewrite, gate and
decision calls.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW ai_spend_daily AS
        SELECT date AS day, feature,
               SUM(requests)::bigint AS calls,
               SUM(tokens_in)::bigint AS tokens_in,
               SUM(tokens_out)::bigint AS tokens_out
          FROM usage_daily
         WHERE feature IN ('improve', 'followups')
         GROUP BY date, feature
        UNION ALL
        SELECT created_at::date AS day, 'answer' AS feature,
               COUNT(*)::bigint AS calls,
               COALESCE(SUM(tokens_in), 0)::bigint AS tokens_in,
               COALESCE(SUM(tokens_out), 0)::bigint AS tokens_out
          FROM messages
         WHERE role = 'assistant' AND NOT from_cache
         GROUP BY created_at::date
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW ai_spend_daily")
