"""Add concise product marketing information."""
from alembic import op
import sqlalchemy as sa

revision = "0007_product_marketing"
down_revision = "0006_product_colors"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("tagline", sa.String(length=160), nullable=True))
    op.add_column("products", sa.Column("selling_points", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade():
    op.drop_column("products", "selling_points")
    op.drop_column("products", "tagline")
