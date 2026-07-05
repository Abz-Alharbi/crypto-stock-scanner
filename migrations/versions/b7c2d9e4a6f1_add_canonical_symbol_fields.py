"""add canonical symbol fields

Revision ID: b7c2d9e4a6f1
Revises: ec83a758dcbd
Create Date: 2026-07-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b7c2d9e4a6f1"
down_revision = "ec83a758dcbd"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("scan_results", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider_symbol", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("display_symbol", sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f("ix_scan_results_provider_symbol"), ["provider_symbol"], unique=False)

    with op.batch_alter_table("watchlists", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider_symbol", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("display_symbol", sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f("ix_watchlists_provider_symbol"), ["provider_symbol"], unique=False)

    op.execute(
        """
        UPDATE scan_results
        SET provider_symbol = CASE
            WHEN market = 'crypto' AND symbol NOT LIKE 'X:%' THEN 'X:' || symbol
            ELSE symbol
        END
        WHERE provider_symbol IS NULL
        """
    )
    op.execute(
        """
        UPDATE scan_results
        SET display_symbol = CASE
            WHEN provider_symbol LIKE 'X:%' THEN substr(provider_symbol, 3)
            ELSE provider_symbol
        END
        WHERE display_symbol IS NULL
        """
    )
    op.execute(
        """
        UPDATE watchlists
        SET provider_symbol = CASE
            WHEN market = 'crypto' AND symbol NOT LIKE 'X:%' AND symbol NOT LIKE '%USD' THEN 'X:' || symbol || 'USD'
            WHEN market = 'crypto' AND symbol NOT LIKE 'X:%' THEN 'X:' || symbol
            ELSE symbol
        END
        WHERE provider_symbol IS NULL
        """
    )
    op.execute(
        """
        UPDATE watchlists
        SET display_symbol = CASE
            WHEN provider_symbol LIKE 'X:%' THEN substr(provider_symbol, 3)
            ELSE provider_symbol
        END
        WHERE display_symbol IS NULL
        """
    )
    op.execute("UPDATE watchlists SET symbol = provider_symbol WHERE provider_symbol IS NOT NULL")

    with op.batch_alter_table("watchlists", schema=None) as batch_op:
        batch_op.alter_column(
            "provider_symbol",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        batch_op.alter_column(
            "display_symbol",
            existing_type=sa.String(length=20),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("watchlists", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_watchlists_provider_symbol"))
        batch_op.drop_column("display_symbol")
        batch_op.drop_column("provider_symbol")

    with op.batch_alter_table("scan_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scan_results_provider_symbol"))
        batch_op.drop_column("display_symbol")
        batch_op.drop_column("provider_symbol")
