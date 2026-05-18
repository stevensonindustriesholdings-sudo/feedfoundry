"""Seed production smoke organisation for launch YouTube intake.

Revision ID: 012_seed_smoke_org
Revises: 011_repair_youtube_source_queue
Create Date: 2026-05-18

Forward-only, idempotent bootstrap for the explicitly documented launch smoke
org. This avoids raw FK failures when operators submit X-Org-Id:
org_smoke_feedfoundry_launch during production smoke tests.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "012_seed_smoke_org"
down_revision: Union[str, None] = "011_repair_youtube_source_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SMOKE_ORG_ID = "org_smoke_feedfoundry_launch"
SMOKE_USER_ID = "user_smoke_feedfoundry_launch"
SMOKE_WALLET_ID = "wal_smoke_feedfoundry_launch"
SMOKE_ANNUAL_ACCESS_ID = "aa_smoke_feedfoundry_launch"
SMOKE_PROCESSING_MINUTES = 3000


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        text(
            """
            INSERT INTO organisations (id, name, slug, owner_user_id, created_at, updated_at)
            VALUES (
                :org_id,
                'FeedFoundry Launch Smoke Org',
                'smoke-feedfoundry-launch',
                :user_id,
                now(),
                now()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(org_id=SMOKE_ORG_ID, user_id=SMOKE_USER_ID)
    )

    op.execute(
        text(
            """
            INSERT INTO users (id, organisation_id, email, role, base44_user_id, created_at, updated_at)
            VALUES (
                :user_id,
                :org_id,
                'smoke@feedfoundry.local',
                'OWNER',
                NULL,
                now(),
                now()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(user_id=SMOKE_USER_ID, org_id=SMOKE_ORG_ID)
    )

    op.execute(
        text(
            """
            INSERT INTO annual_access (
                id,
                organisation_id,
                plan_code,
                status,
                period_start,
                period_end,
                hosting_until,
                included_processing_minutes_annual,
                stripe_checkout_session_id,
                stripe_subscription_id,
                stripe_payment_intent_id,
                created_at,
                updated_at
            )
            VALUES (
                :aa_id,
                :org_id,
                'creator_core',
                'ACTIVE',
                now(),
                now() + interval '365 days',
                now() + interval '365 days',
                :minutes,
                NULL,
                NULL,
                NULL,
                now(),
                now()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(aa_id=SMOKE_ANNUAL_ACCESS_ID, org_id=SMOKE_ORG_ID, minutes=SMOKE_PROCESSING_MINUTES)
    )

    op.execute(
        text(
            """
            INSERT INTO credit_wallets (
                id,
                organisation_id,
                processing_minutes_available,
                processing_minutes_reserved,
                processing_minutes_spent_lifetime,
                processing_minutes_expired_lifetime,
                currency,
                updated_at
            )
            VALUES (
                :wallet_id,
                :org_id,
                :minutes,
                0,
                0,
                0,
                'FF_PROCESSING_MINUTE',
                now()
            )
            ON CONFLICT (organisation_id) DO NOTHING
            """
        ).bindparams(wallet_id=SMOKE_WALLET_ID, org_id=SMOKE_ORG_ID, minutes=SMOKE_PROCESSING_MINUTES)
    )


def downgrade() -> None:
    # Forward-only smoke bootstrap; do not remove production account rows.
    return
