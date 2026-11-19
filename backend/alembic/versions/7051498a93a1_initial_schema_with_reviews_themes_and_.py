"""Initial schema with reviews, themes, and alert_configs

Revision ID: 7051498a93a1
Revises: 
Create Date: 2026-11-19 14:24:35.849955

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7051498a93a1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade database schema.
    Supports both:
      1. A completely fresh database (creates all tables, indexes, and constraints).
      2. An existing legacy database (adds theme_confidence and missing components safely).
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. alert_configs table
    if "alert_configs" not in existing_tables:
        op.create_table(
            "alert_configs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("slack_webhook_url", sa.String(length=255), nullable=True),
            sa.Column("negative_threshold_pct", sa.Float(), nullable=False, server_default="30.0"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index(op.f("ix_alert_configs_id"), "alert_configs", ["id"], unique=False)

    # 2. themes table
    if "themes" not in existing_tables:
        op.create_table(
            "themes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("owner_team", sa.String(length=100), nullable=True),
            sa.Column("jira_component_id", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, default=datetime.utcnow),
        )
        op.create_index(op.f("ix_themes_id"), "themes", ["id"], unique=False)
        op.create_index(op.f("ix_themes_name"), "themes", ["name"], unique=True)

    # 3. reviews table
    if "reviews" not in existing_tables:
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("author", sa.String(length=100), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True, default=datetime.utcnow),
            sa.Column("sentiment_score", sa.Float(), nullable=False),
            sa.Column("sentiment_label", sa.String(length=20), nullable=False),
            sa.Column("category_theme", sa.String(length=50), nullable=False),
            sa.Column("theme_confidence", sa.Float(), nullable=True, server_default="1.0"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="New"),
            sa.CheckConstraint(
                "status IN ('New', 'Investigating', 'Escalated', 'Resolved')",
                name="check_review_status",
            ),
            sa.CheckConstraint(
                "sentiment_label IN ('Positive', 'Neutral', 'Negative')",
                name="check_sentiment_label",
            ),
            sa.CheckConstraint(
                "source IN ('App Store', 'Google Play', 'Reddit', 'Discord')",
                name="check_source",
            ),
            sa.CheckConstraint(
                "rating IS NULL OR (rating >= 1 AND rating <= 5)",
                name="check_rating_range",
            ),
        )
        op.create_index(op.f("ix_reviews_id"), "reviews", ["id"], unique=False)
        op.create_index(op.f("ix_reviews_source"), "reviews", ["source"], unique=False)
        op.create_index(op.f("ix_reviews_sentiment_label"), "reviews", ["sentiment_label"], unique=False)
        op.create_index(op.f("ix_reviews_category_theme"), "reviews", ["category_theme"], unique=False)
        op.create_index(op.f("ix_reviews_status"), "reviews", ["status"], unique=False)
        op.create_index(op.f("ix_reviews_created_at"), "reviews", ["created_at"], unique=False)
    else:
        # Reviews table already existed from legacy schema; check for theme_confidence
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" not in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.add_column(sa.Column("theme_confidence", sa.Float(), nullable=True, server_default="1.0"))


def downgrade() -> None:
    """
    Downgrade schema.
    Safely removes theme_confidence if added to an existing table,
    or drops tables if cleanly rolling back.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "reviews" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.drop_column("theme_confidence")
