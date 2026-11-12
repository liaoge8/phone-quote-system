"""Add image url to product colors."""
from alembic import op
import sqlalchemy as sa

revision = "0009_color_image_url"
down_revision = "0008_product_official_price"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_colors", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("product_colors", "image_url")
