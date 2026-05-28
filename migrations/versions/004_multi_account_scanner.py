"""Multi-account tables and account_id on positions/orders."""

from alembic import op
import sqlalchemy as sa

revision = "004_multi_account"
down_revision = "003_ratio_swaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("display_name", sa.String(128), nullable=False, server_default="default"),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "exchange_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default="account"),
        sa.Column("exchange", sa.String(32), nullable=False, server_default="bybit"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_secret_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("trading_mode", sa.String(8), nullable=False, server_default="paper"),
        sa.Column("live_trading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("copy_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("order_usdt", sa.Float(), nullable=False, server_default="100"),
        sa.Column("position_size_mode", sa.String(32), nullable=False, server_default="fixed_usdt"),
        sa.Column("max_open_positions", sa.Integer(), nullable=True),
        sa.Column("paper_initial_balance", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_exchange_accounts_user_id", "exchange_accounts", ["user_id"])

    with op.batch_alter_table("positions") as batch:
        batch.add_column(sa.Column("account_id", sa.Integer(), server_default="1", nullable=False))
        batch.create_index("ix_positions_account_id", ["account_id"])
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("account_id", sa.Integer(), server_default="1", nullable=False))
        batch.create_index("ix_orders_account_id", ["account_id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_account_id")
        batch.drop_column("account_id")
    with op.batch_alter_table("positions") as batch:
        batch.drop_index("ix_positions_account_id")
        batch.drop_column("account_id")
    op.drop_table("exchange_accounts")
    op.drop_table("users")
