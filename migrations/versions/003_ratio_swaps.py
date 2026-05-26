"""Ratio monitoring and swap proposals."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_ratio_swaps"
down_revision: Union[str, None] = "002_position_explanations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pair_ratio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_asset", sa.String(16), nullable=False),
        sa.Column("quote_asset", sa.String(16), nullable=False),
        sa.Column("ratio", sa.Float(), nullable=False),
        sa.Column("base_price_usdt", sa.Float(), nullable=False),
        sa.Column("quote_price_usdt", sa.Float(), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.UniqueConstraint("base_asset", "quote_asset", "sampled_at", name="uq_pair_ratio_sample"),
    )
    op.create_index("ix_pair_ratio_base_quote", "pair_ratio_snapshots", ["base_asset", "quote_asset"])

    op.create_table(
        "ratio_swap_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("base_asset", sa.String(16), nullable=False),
        sa.Column("quote_asset", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("from_asset", sa.String(16), nullable=False),
        sa.Column("to_asset", sa.String(16), nullable=False),
        sa.Column("from_qty", sa.Float(), nullable=False),
        sa.Column("to_qty", sa.Float(), nullable=False),
        sa.Column("ratio_current", sa.Float(), nullable=False),
        sa.Column("ratio_mean", sa.Float(), nullable=True),
        sa.Column("ratio_min_hist", sa.Float(), nullable=True),
        sa.Column("ratio_max_hist", sa.Float(), nullable=True),
        sa.Column("ratio_percentile", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ratio_swap_status", "ratio_swap_proposals", ["status"])

    op.create_table(
        "asset_holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset", sa.String(16), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("trading_mode", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset", "trading_mode", name="uq_asset_mode"),
    )


def downgrade() -> None:
    op.drop_table("asset_holdings")
    op.drop_table("ratio_swap_proposals")
    op.drop_table("pair_ratio_snapshots")
