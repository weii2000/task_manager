"""add user long-term memories

Revision ID: a41d8b75e210
Revises: 6c84f50a102d
Create Date: 2026-07-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a41d8b75e210"
down_revision: Union[str, Sequence[str], None] = "6c84f50a102d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("memory_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "profile",
                "preference",
                "constraint",
                "long_term_goal",
                name="memorycategory",
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "archived",
                name="memorystatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "conversation",
                name="memorysource",
            ),
            nullable=False,
        ),
        sa.Column("source_agent_session_id", sa.Integer(), nullable=True),
        sa.Column("source_message_index", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_user_memories_positive_version",
        ),
        sa.CheckConstraint(
            "source_message_index IS NULL OR source_message_index >= 0",
            name="ck_user_memories_nonnegative_message_index",
        ),
        sa.ForeignKeyConstraint(
            ["source_agent_session_id"],
            ["agent_session.session_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("memory_id"),
    )
    op.create_index(
        "ix_user_memories_user_status_updated",
        "user_memories",
        ["user_id", "status", "updated_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_memories_user_status_updated",
        table_name="user_memories",
    )
    op.drop_table("user_memories")
