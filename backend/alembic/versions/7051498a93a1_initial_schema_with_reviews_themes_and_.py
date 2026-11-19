"""Initial schema with reviews, themes, and alert_configs

Revision ID: 7051498a93a1
Revises: 
Create Date: 2026-11-19 14:24:35.849955

"""
from typing import Sequence, Union, Optional
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7051498a93a1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

METADATA_TABLE = "_alembic_migration_metadata"
STATE_TABLE = f"_alembic_rev_{revision}_state"


def upgrade() -> None:
    """
    Upgrade database schema.
    Uses an isolated state table (_alembic_rev_7051498a93a1_state) to track exact
    ownership of created objects. If _alembic_migration_metadata already exists in
    a legacy database, it is left completely untouched to prevent any key collisions.
    If it did not exist, it is created and dropped on downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # Create isolated revision state tracker
    state_table_def = sa.table(
        STATE_TABLE,
        sa.column("key", sa.String),
        sa.column("created_by_migration", sa.Boolean),
    )

    if STATE_TABLE not in existing_tables:
        op.create_table(
            STATE_TABLE,
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("created_by_migration", sa.Boolean(), nullable=False),
        )

    meta_table_existed = METADATA_TABLE in existing_tables
    meta_table = sa.table(
        METADATA_TABLE,
        sa.column("key", sa.String),
        sa.column("value", sa.String),
    )

    if not meta_table_existed:
        op.create_table(
            METADATA_TABLE,
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.String(length=100), nullable=False),
        )
        conn.execute(meta_table.insert().values(key="created_metadata_table", value="1"))

    # Record metadata table creation ownership in isolated state tracker
    conn.execute(
        state_table_def.insert().values(
            key="metadata_table",
            created_by_migration=not meta_table_existed,
        )
    )

    def record_action(action_key: str, created: bool, meta_value: str) -> None:
        """Records state in isolated tracker table and populates metadata table if newly created."""
        conn.execute(
            state_table_def.insert().values(
                key=action_key,
                created_by_migration=created,
            )
        )
        if not meta_table_existed:
            conn.execute(meta_table.insert().values(key=action_key, value=meta_value))

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
        record_action("created_alert_configs", True, "1")

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
    else:
        record_action("created_alert_configs", False, "0")

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
        record_action("created_themes", True, "1")

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
    else:
        record_action("created_themes", False, "0")

    # 3. reviews table
    if "reviews" not in existing_tables:
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("author", sa.String(length=100), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("sentiment_score", sa.Float(), nullable=False),
            sa.Column("sentiment_label", sa.String(length=20), nullable=False),
            sa.Column("category_theme", sa.String(length=100), nullable=False),
            sa.Column("theme_confidence", sa.Float(), nullable=True, server_default="1.0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="New"),
            sa.Column("created_at", sa.DateTime(), nullable=True, default=datetime.utcnow),
        )
        op.create_index(op.f("ix_reviews_id"), "reviews", ["id"], unique=False)
        op.create_index(op.f("ix_reviews_source"), "reviews", ["source"], unique=False)
        op.create_index(op.f("ix_reviews_sentiment_label"), "reviews", ["sentiment_label"], unique=False)
        op.create_index(op.f("ix_reviews_category_theme"), "reviews", ["category_theme"], unique=False)
        op.create_index(op.f("ix_reviews_status"), "reviews", ["status"], unique=False)
        op.create_index(op.f("ix_reviews_created_at"), "reviews", ["created_at"], unique=False)
        record_action("created_reviews", True, "1")
    else:
        record_action("created_reviews", False, "0")
        # Reviews table already existed from legacy schema; check for theme_confidence
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" not in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.add_column(sa.Column("theme_confidence", sa.Float(), nullable=True, server_default="1.0"))
            record_action("added_theme_confidence", True, "1")
        else:
            record_action("added_theme_confidence", False, "0")


def downgrade() -> None:
    """
    Downgrade schema.
    Reads from the dedicated state table (_alembic_rev_7051498a93a1_state) to reverse
    only the mutations performed during this migration:
    - If theme_confidence was added by this migration, removes it.
    - If theme_confidence existed prior to this migration, preserves it.
    - If tables were created by this migration, drops them.
    - If tables were pre-existing legacy tables, preserves them and their data.
    - If metadata table was created by this migration, drops it. If pre-existing, leaves it untouched.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    state_table_def = sa.table(
        STATE_TABLE,
        sa.column("key", sa.String),
        sa.column("created_by_migration", sa.Boolean),
    )

    actions = {}
    if STATE_TABLE in existing_tables:
        try:
            res = conn.execute(
                sa.select(
                    state_table_def.c.key,
                    state_table_def.c.created_by_migration,
                )
            ).fetchall()
            actions = {
                row[0]: bool(row[1])
                for row in res
            }
        except Exception:
            actions = {}

    def owns(name: str) -> bool:
        return bool(actions.get(name, False))

    # 1. Reverse theme_confidence column only if added by this migration
    if owns("added_theme_confidence") and "reviews" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("reviews")}
        if "theme_confidence" in existing_columns:
            with op.batch_alter_table("reviews") as batch_op:
                batch_op.drop_column("theme_confidence")

    # 2. Reverse table creations only if created by this migration
    if owns("created_reviews") and "reviews" in existing_tables:
        op.drop_table("reviews")

    if owns("created_themes") and "themes" in existing_tables:
        op.drop_table("themes")

    if owns("created_alert_configs") and "alert_configs" in existing_tables:
        op.drop_table("alert_configs")

    # 3. Clean up metadata tracking table ONLY if this migration created it
    if owns("metadata_table") and METADATA_TABLE in existing_tables:
        op.drop_table(METADATA_TABLE)

    # 4. Drop state snapshot table
    if STATE_TABLE in existing_tables:
        op.drop_table(STATE_TABLE)
