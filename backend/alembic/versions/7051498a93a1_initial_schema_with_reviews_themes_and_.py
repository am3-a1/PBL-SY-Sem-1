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

METADATA_TABLE = "_alembic_migration_metadata"


def upgrade() -> None:
    """
    Upgrade database schema.
    Tracks all created objects in _alembic_migration_metadata so that downgrade
    is strictly reversible and NEVER destroys pre-existing legacy user tables/data.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    meta_table = sa.table(
        METADATA_TABLE,
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )

    # Create internal metadata tracker table
    if METADATA_TABLE not in existing_tables:
        op.create_table(
            METADATA_TABLE,
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.String(length=100), nullable=False),
        )
        op.bulk_insert(meta_table, [{"key": "created_metadata_table", "value": "1"}])

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
        op.bulk_insert(meta_table, [{"key": "created_alert_configs", "value": "1"}])

        # Seed default alert config on fresh table creation
        alert_table = sa.table(
            "alert_configs",
            sa.column("slack_webhook_url", sa.String),
            sa.column("negative_threshold_pct", sa.Float),
            sa.column("is_enabled", sa.Boolean),
        )
        op.bulk_insert(alert_table, [{
            "slack_webhook_url": None,
            "negative_threshold_pct": 30.0,
            "is_enabled": True,
        }])

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
        op.bulk_insert(meta_table, [{"key": "created_themes", "value": "1"}])

        # Seed default themes on fresh table creation
        theme_table = sa.table(
            "themes",
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("owner_team", sa.String),
            sa.column("jira_component_id", sa.String),
            sa.column("created_at", sa.DateTime),
        )
        now = datetime.utcnow()
        op.bulk_insert(theme_table, [
            {"name": "Login Crash", "description": "Authentication failures, crashes on launch, session termination, biometric login issues", "owner_team": "Auth Squad", "jira_component_id": "AUTH-CRASH", "created_at": now},
            {"name": "Billing & Payments", "description": "In-app purchases, subscriptions, double charges, refunds, receipts", "owner_team": "Finance Squad", "jira_component_id": "FIN-BILLING", "created_at": now},
            {"name": "Performance & Lag", "description": "Frame drops, latency, memory leaks, thermal throttling, loading spinners", "owner_team": "Core Platform", "jira_component_id": "PLAT-PERF", "created_at": now},
            {"name": "UI/UX", "description": "Layout confusion, gesture navigation, contrast, readability, visual styling", "owner_team": "Design Squad", "jira_component_id": "UIUX-EXP", "created_at": now},
            {"name": "General", "description": "General feedback, mixed commentary, and unclassified feedback", "owner_team": "Customer Support", "jira_component_id": "CS-GENERAL", "created_at": now},
        ])

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
        op.bulk_insert(meta_table, [{"key": "created_reviews", "value": "1"}])
    else:
        # Reviews table already existed from legacy schema; check for theme_confidence
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" not in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.add_column(sa.Column("theme_confidence", sa.Float(), nullable=True, server_default="1.0"))
            op.bulk_insert(meta_table, [{"key": "added_theme_confidence", "value": "1"}])


def downgrade() -> None:
    """
    Downgrade schema.
    Strictly reverses only the mutations performed during this migration:
    - If theme_confidence was added by this migration, removes it.
    - If theme_confidence existed prior to this migration, preserves it.
    - If tables were created by this migration, drops them.
    - If tables were pre-existing legacy tables, preserves them and their data.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    actions = {}
    if METADATA_TABLE in existing_tables:
        meta_table = sa.table(
            METADATA_TABLE,
            sa.column("key", sa.String),
            sa.column("value", sa.String),
        )
        res = conn.execute(sa.select(meta_table.c.key, meta_table.c.value)).fetchall()
        actions = {row[0]: row[1] for row in res}

    # 1. Reverse theme_confidence column only if added by this migration
    if actions.get("added_theme_confidence") == "1" and "reviews" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.drop_column("theme_confidence")

    # 2. Reverse table creations only if created by this migration
    if actions.get("created_reviews") == "1" and "reviews" in existing_tables:
        op.drop_table("reviews")

    if actions.get("created_themes") == "1" and "themes" in existing_tables:
        op.drop_table("themes")

    if actions.get("created_alert_configs") == "1" and "alert_configs" in existing_tables:
        op.drop_table("alert_configs")

    # 3. Clean up metadata tracking table ONLY if this migration created it
    if actions.get("created_metadata_table") == "1" and METADATA_TABLE in existing_tables:
        op.drop_table(METADATA_TABLE)
    elif METADATA_TABLE in existing_tables:
        # Pre-existing metadata table: remove only the keys inserted by this migration
        keys_to_clean = [
            "created_reviews",
            "created_themes",
            "created_alert_configs",
            "added_theme_confidence",
            "created_metadata_table",
        ]
        try:
            conn.execute(meta_table.delete().where(meta_table.c.key.in_(keys_to_clean)))
        except Exception:
            pass
