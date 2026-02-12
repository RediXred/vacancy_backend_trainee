"""create vacancies table

Revision ID: 0001_create_vacancies
Revises: 
Create Date: 2026-02-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_vacancies"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("timetable_mode_name", sa.String(), nullable=False),
        sa.Column("tag_name", sa.String(), nullable=False),
        sa.Column("city_name", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_remote_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_hot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("external_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("external_id", name="uq_vacancies_external_id"),
    )


def downgrade() -> None:
    op.drop_table("vacancies")
