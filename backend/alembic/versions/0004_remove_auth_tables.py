"""remove authentication tables

Revision ID: 0004_remove_auth_tables
Revises: 0003_auth_tables
Create Date: 2026-07-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_remove_auth_tables"
down_revision = "0003_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_auth_sessions_token_jti")
    op.execute("DROP INDEX IF EXISTS ix_auth_sessions_user_id")
    op.execute("DROP TABLE IF EXISTS auth_sessions")
    op.execute("DROP INDEX IF EXISTS ix_users_role")
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.execute("DROP TABLE IF EXISTS users")


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_jti", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id", ondelete="CASCADE"),
        sa.UniqueConstraint("token_jti", name="uq_auth_sessions_token_jti"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_jti", "auth_sessions", ["token_jti"])
