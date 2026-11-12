"""Add per-variant official price."""
from alembic import op
import sqlalchemy as sa

revision = "0010_variant_official_price"
down_revision = "0009_color_image_url"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_variants", sa.Column("official_price", sa.Numeric(12, 2), nullable=True))


def downgrade():
    op.drop_column("product_variants", "official_price")
