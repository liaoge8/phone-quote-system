"""Add monthly policy price archive."""
from alembic import op
import sqlalchemy as sa

revision = "0002_policy_prices"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variant", sa.String(100), nullable=False),
        sa.Column("effective_month", sa.Date(), nullable=False),
        sa.Column("policy_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("void_reason", sa.Text()),
    )
    op.create_index("ix_policy_prices_product_id", "policy_prices", ["product_id"])
    op.create_index("ix_policy_prices_effective_month", "policy_prices", ["effective_month"])


def downgrade():
    op.drop_index("ix_policy_prices_effective_month", table_name="policy_prices")
    op.drop_index("ix_policy_prices_product_id", table_name="policy_prices")
    op.drop_table("policy_prices")
