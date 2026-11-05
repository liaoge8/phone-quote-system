"""Allow multiple dated policy changes and store screenshot evidence metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0003_policy_evidence"
down_revision = "0002_policy_prices"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_policy_prices_active_product_variant_month", table_name="policy_prices")
    op.add_column("policy_prices", sa.Column("effective_date", sa.Date(), nullable=True))
    op.add_column("policy_prices", sa.Column("interpretation", sa.Text(), nullable=True))
    op.execute("UPDATE policy_prices SET effective_date = effective_month WHERE effective_date IS NULL")
    op.execute("UPDATE policy_prices SET interpretation = COALESCE(note, '历史政策记录：原系统未保存独立政策解读字段') WHERE interpretation IS NULL")
    with op.batch_alter_table("policy_prices") as batch:
        batch.alter_column("effective_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("interpretation", existing_type=sa.Text(), nullable=False)
    op.create_index("ix_policy_prices_effective_date", "policy_prices", ["effective_date"])
    op.create_table(
        "policy_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_price_id", sa.Integer(), sa.ForeignKey("policy_prices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False, unique=True),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_policy_evidence_policy_price_id", "policy_evidence", ["policy_price_id"])


def downgrade():
    op.drop_index("ix_policy_evidence_policy_price_id", table_name="policy_evidence")
    op.drop_table("policy_evidence")
    op.drop_index("ix_policy_prices_effective_date", table_name="policy_prices")
    with op.batch_alter_table("policy_prices") as batch:
        batch.drop_column("interpretation")
        batch.drop_column("effective_date")
    op.create_index(
        "uq_policy_prices_active_product_variant_month",
        "policy_prices",
        ["product_id", "variant", "effective_month"],
        unique=True,
        sqlite_where=sa.text("voided_at IS NULL"),
        postgresql_where=sa.text("voided_at IS NULL"),
    )
