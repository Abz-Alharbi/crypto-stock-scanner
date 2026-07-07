"""add universe symbols

Revision ID: d3a6f1c2b8e9
Revises: c4f7b820de31
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d3a6f1c2b8e9"
down_revision = "c4f7b820de31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "universe_symbols",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("avg_daily_volume", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("exchange IN ('NASDAQ', 'NYSE')", name="ck_universe_symbols_exchange"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange", "rank", name="uq_universe_symbols_exchange_rank"),
        sa.UniqueConstraint("symbol", name="uq_universe_symbols_symbol"),
    )
    with op.batch_alter_table("universe_symbols", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_universe_symbols_computed_at"), ["computed_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_universe_symbols_exchange"), ["exchange"], unique=False)
        batch_op.create_index(batch_op.f("ix_universe_symbols_symbol"), ["symbol"], unique=False)


def downgrade():
    with op.batch_alter_table("universe_symbols", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_universe_symbols_symbol"))
        batch_op.drop_index(batch_op.f("ix_universe_symbols_exchange"))
        batch_op.drop_index(batch_op.f("ix_universe_symbols_computed_at"))
    op.drop_table("universe_symbols")
