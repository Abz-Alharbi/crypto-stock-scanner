"""generalize universe symbols

Revision ID: f5c8d2a1b7e4
Revises: e4f2a9b7c6d1
Create Date: 2026-07-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f5c8d2a1b7e4"
down_revision = "e4f2a9b7c6d1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("universe_symbols", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "asset_class",
                sa.String(length=10),
                nullable=True,
                server_default="equity",
            )
        )
        batch_op.add_column(sa.Column("venue", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("quote_currency", sa.String(length=10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("universe_key", sa.String(length=64), nullable=True)
        )

    op.execute("UPDATE universe_symbols SET asset_class = 'equity'")
    op.execute(
        "UPDATE universe_symbols SET venue = CASE "
        "WHEN exchange = 'NASDAQ' THEN 'XNAS' "
        "WHEN exchange = 'NYSE' THEN 'XNYS' ELSE NULL END"
    )
    op.execute(
        "UPDATE universe_symbols SET universe_key = CASE "
        "WHEN exchange = 'NASDAQ' THEN 'nasdaq_top' "
        "WHEN exchange = 'NYSE' THEN 'nyse_top' ELSE 'us_stocks_top' END"
    )

    with op.batch_alter_table("universe_symbols", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_universe_symbols_exchange", type_="check"
        )
        batch_op.drop_constraint(
            "uq_universe_symbols_exchange_rank", type_="unique"
        )
        batch_op.alter_column(
            "asset_class",
            existing_type=sa.String(length=10),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "universe_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.alter_column(
            "exchange",
            existing_type=sa.String(length=10),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_universe_symbols_asset_class",
            "asset_class IN ('equity', 'crypto')",
        )
        batch_op.create_unique_constraint(
            "uq_universe_symbols_universe_rank", ["universe_key", "rank"]
        )
        batch_op.create_index(
            batch_op.f("ix_universe_symbols_asset_class"),
            ["asset_class"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_universe_symbols_venue"), ["venue"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_universe_symbols_universe_key"),
            ["universe_key"],
            unique=False,
        )


def downgrade():
    # The old schema cannot represent non-equity constituents.
    op.execute("DELETE FROM universe_symbols WHERE asset_class != 'equity'")
    op.execute(
        "UPDATE universe_symbols SET exchange = CASE "
        "WHEN venue = 'XNAS' THEN 'NASDAQ' "
        "WHEN venue = 'XNYS' THEN 'NYSE' ELSE exchange END"
    )
    op.execute(
        "DELETE FROM universe_symbols "
        "WHERE exchange NOT IN ('NASDAQ', 'NYSE') OR exchange IS NULL"
    )

    with op.batch_alter_table("universe_symbols", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_universe_symbols_universe_key"))
        batch_op.drop_index(batch_op.f("ix_universe_symbols_venue"))
        batch_op.drop_index(batch_op.f("ix_universe_symbols_asset_class"))
        batch_op.drop_constraint(
            "uq_universe_symbols_universe_rank", type_="unique"
        )
        batch_op.drop_constraint(
            "ck_universe_symbols_asset_class", type_="check"
        )
        batch_op.alter_column(
            "exchange",
            existing_type=sa.String(length=10),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_universe_symbols_exchange",
            "exchange IN ('NASDAQ', 'NYSE')",
        )
        batch_op.create_unique_constraint(
            "uq_universe_symbols_exchange_rank", ["exchange", "rank"]
        )
        batch_op.drop_column("universe_key")
        batch_op.drop_column("quote_currency")
        batch_op.drop_column("venue")
        batch_op.drop_column("asset_class")
