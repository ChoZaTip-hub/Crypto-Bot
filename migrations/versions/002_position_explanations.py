"""Add entry/exit explanation columns to positions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_position_explanations"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("entry_explanation", sa.Text(), nullable=True))
    op.add_column("positions", sa.Column("exit_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("positions", "exit_explanation")
    op.drop_column("positions", "entry_explanation")
