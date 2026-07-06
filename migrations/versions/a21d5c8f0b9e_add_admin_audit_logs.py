"""add admin audit logs

Revision ID: a21d5c8f0b9e
Revises: b7c2d9e4a6f1
Create Date: 2026-07-06 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a21d5c8f0b9e"
down_revision = "b7c2d9e4a6f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_admin_audit_logs_admin_user_id"), ["admin_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_admin_audit_logs_created_at"), ["created_at"], unique=False)


def downgrade():
    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_admin_audit_logs_created_at"))
        batch_op.drop_index(batch_op.f("ix_admin_audit_logs_admin_user_id"))
    op.drop_table("admin_audit_logs")
