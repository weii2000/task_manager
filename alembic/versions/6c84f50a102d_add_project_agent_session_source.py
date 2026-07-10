"""add agent execution persistence support

Revision ID: 6c84f50a102d
Revises: 1951cfcb707c
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "6c84f50a102d"
down_revision: Union[str, Sequence[str], None] = "1951cfcb707c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand Agent state and add execution provenance/idempotency."""
    op.alter_column(
        "agent_session",
        "state_json",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT(),
        existing_nullable=False,
    )
    op.add_column(
        "projects",
        sa.Column("source_agent_session_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_source_agent_session_id_agent_session",
        "projects",
        "agent_session",
        ["source_agent_session_id"],
        ["session_id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_projects_source_agent_session_id",
        "projects",
        ["source_agent_session_id"],
    )


def downgrade() -> None:
    """Remove Agent execution persistence support."""
    op.drop_constraint(
        "uq_projects_source_agent_session_id",
        "projects",
        type_="unique",
    )
    op.drop_constraint(
        "fk_projects_source_agent_session_id_agent_session",
        "projects",
        type_="foreignkey",
    )
    op.drop_column("projects", "source_agent_session_id")
    op.alter_column(
        "agent_session",
        "state_json",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
