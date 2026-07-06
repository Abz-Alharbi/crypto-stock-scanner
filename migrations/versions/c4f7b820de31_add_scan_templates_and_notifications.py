"""add scan templates and notifications

Revision ID: c4f7b820de31
Revises: a21d5c8f0b9e
Create Date: 2026-07-06 17:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4f7b820de31"
down_revision = "a21d5c8f0b9e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scan_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("criteria_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scan_templates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scan_templates_user_id"), ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_dedupe_key"), ["dedupe_key"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_read_at"), ["read_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_user_id"), ["user_id"], unique=False)


def downgrade():
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notifications_user_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_read_at"))
        batch_op.drop_index(batch_op.f("ix_notifications_dedupe_key"))
        batch_op.drop_index(batch_op.f("ix_notifications_created_at"))
    op.drop_table("notifications")

    with op.batch_alter_table("scan_templates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scan_templates_user_id"))
    op.drop_table("scan_templates")
