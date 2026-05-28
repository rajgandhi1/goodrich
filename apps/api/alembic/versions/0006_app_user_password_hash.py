"""Add app user password hash.

Revision ID: 0006_app_user_password_hash
Revises: 0005_app_user_profile_fields
Create Date: 2026-05-28
"""
from __future__ import annotations

from alembic import op

revision = "0006_app_user_password_hash"
down_revision = "0005_app_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table app_users add column if not exists password_hash text not null default ''")
    op.execute(
        """
        do $$
        begin
            if exists (
                select 1
                from information_schema.columns
                where table_name = 'app_users' and column_name = 'password'
            ) then
                update app_users
                set password_hash = 'plain:' || password
                where password_hash = '' and password is not null and password <> '';
            end if;
        end $$;
        """
    )


def downgrade() -> None:
    op.execute("alter table app_users drop column if exists password_hash")
