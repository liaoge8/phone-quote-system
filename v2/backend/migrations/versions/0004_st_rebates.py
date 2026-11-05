"""Add optional ST rebate history."""
from alembic import op
import sqlalchemy as sa

revision = "0004_st_rebates"
down_revision = "0003_policy_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "st_rebates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variant", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_st_rebates_product_id", "st_rebates", ["product_id"])
    op.create_index("ix_st_rebates_effective_date", "st_rebates", ["effective_date"])


def downgrade():
    op.drop_index("ix_st_rebates_effective_date", table_name="st_rebates")
    op.drop_index("ix_st_rebates_product_id", table_name="st_rebates")
    op.drop_table("st_rebates")
