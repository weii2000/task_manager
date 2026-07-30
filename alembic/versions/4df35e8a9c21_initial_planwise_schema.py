"""Initial Planwise schema.

Revision ID: 4df35e8a9c21
Revises:
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op


revision: str = "4df35e8a9c21"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("hashed_password", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=50), nullable=True),
        sa.Column("bio", sa.String(length=100), nullable=True),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "agent_session",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "state_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_table(
        "plans",
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("source_agent_session_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "planning",
                "active",
                "paused",
                "completed",
                name="planstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "creation_source",
            sa.Enum(
                "manual",
                "agent",
                "system",
                name="creationsource",
            ),
            nullable=False,
        ),
        sa.Column(
            "system_type",
            sa.Enum("inbox", name="plansystemtype"),
            nullable=True,
        ),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("due_time", sa.DateTime(), nullable=True),
        sa.Column("completed_time", sa.DateTime(), nullable=True),
        sa.Column("archived_time", sa.DateTime(), nullable=True),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "start_time IS NULL OR due_time IS NULL OR due_time >= start_time",
            name="ck_plans_due_after_start",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_agent_session_id"],
            ["agent_session.session_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("plan_id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_plans_owner_idempotency_key",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "system_type",
            name="uq_plans_owner_system_type",
        ),
        sa.UniqueConstraint(
            "source_agent_session_id",
            name="uq_plans_source_agent_session_id",
        ),
    )
    op.create_index(
        op.f("ix_plans_owner_user_id"),
        "plans",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plans_title"),
        "plans",
        ["title"],
        unique=False,
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("refresh_token_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("refresh_token_id"),
        sa.UniqueConstraint("token_hash"),
    )
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
            "source_message_index IS NULL OR source_message_index >= 0",
            name="ck_user_memories_nonnegative_message_index",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_user_memories_positive_version",
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
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "in_progress",
                "blocked",
                "completed",
                "cancelled",
                name="taskstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "low",
                "medium",
                "high",
                "urgent",
                name="taskpriority",
            ),
            nullable=False,
        ),
        sa.Column(
            "creation_source",
            sa.Enum(
                "manual",
                "agent",
                "system",
                name="creationsource",
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("due_time", sa.DateTime(), nullable=True),
        sa.Column("completed_time", sa.DateTime(), nullable=True),
        sa.Column("archived_time", sa.DateTime(), nullable=True),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "level BETWEEN 1 AND 3",
            name="ck_tasks_level",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_tasks_nonnegative_sort_order",
        ),
        sa.CheckConstraint(
            "start_time IS NULL OR due_time IS NULL OR due_time >= start_time",
            name="ck_tasks_due_after_start",
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["tasks.task_id"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.plan_id"],
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(
        op.f("ix_tasks_parent_task_id"),
        "tasks",
        ["parent_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tasks_plan_id"),
        "tasks",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tasks_title"),
        "tasks",
        ["title"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("user_memories")
    op.drop_table("refresh_tokens")
    op.drop_table("plans")
    op.drop_table("agent_session")
    op.drop_table("users")
