"""Add manufacturer color catalogue for products."""
from alembic import op
import sqlalchemy as sa

revision = "0006_product_colors"
down_revision = "0005_product_variants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_colors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("color_name", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "color_name", name="uq_product_color_name"),
    )
    op.create_index("ix_product_colors_product_id", "product_colors", ["product_id"])


def downgrade():
    op.drop_index("ix_product_colors_product_id", table_name="product_colors")
    op.drop_table("product_colors")
