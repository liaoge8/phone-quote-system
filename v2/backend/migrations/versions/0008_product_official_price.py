"""Add official price reference fields to products."""
from alembic import op
import sqlalchemy as sa

revision = "0008_product_official_price"
down_revision = "0007_product_marketing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("official_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("products", sa.Column("official_url", sa.String(length=500), nullable=True))
    op.add_column("products", sa.Column("official_price_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("products", "official_price_updated_at")
    op.drop_column("products", "official_url")
    op.drop_column("products", "official_price")
