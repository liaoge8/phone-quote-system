"""Add structured product variants and link legacy price rows."""
from alembic import op
import sqlalchemy as sa

revision = "0005_product_variants"
down_revision = "0004_st_rebates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("ram", sa.String(20)),
        sa.Column("storage", sa.String(20)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "display_name", name="uq_product_variant_display_name"),
    )
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])

    op.add_column("price_records", sa.Column("variant_id", sa.Integer(), nullable=True))
    op.add_column("policy_prices", sa.Column("variant_id", sa.Integer(), nullable=True))
    op.add_column("st_rebates", sa.Column("variant_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_price_records_variant_id", "price_records", "product_variants", ["variant_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_policy_prices_variant_id", "policy_prices", "product_variants", ["variant_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_st_rebates_variant_id", "st_rebates", "product_variants", ["variant_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_price_records_variant_id", "price_records", ["variant_id"])
    op.create_index("ix_policy_prices_variant_id", "policy_prices", ["variant_id"])
    op.create_index("ix_st_rebates_variant_id", "st_rebates", ["variant_id"])

    conn = op.get_bind()
    rows = conn.execute(sa.text("""
        SELECT product_id, variant FROM price_records
        UNION
        SELECT product_id, variant FROM policy_prices
        UNION
        SELECT product_id, variant FROM st_rebates
    """)).fetchall()
    variant_ids = {}
    for product_id, display_name in rows:
        if not display_name:
            continue
        result = conn.execute(
            sa.text("SELECT id FROM product_variants WHERE product_id=:pid AND display_name=:name"),
            {"pid": product_id, "name": display_name},
        ).first()
        if result:
            variant_id = result[0]
        else:
            variant_id = conn.execute(
                sa.text("INSERT INTO product_variants (product_id, display_name, is_active) VALUES (:pid, :name, :active)"),
                {"pid": product_id, "name": display_name, "active": True},
            ).lastrowid
            if variant_id is None:
                variant_id = conn.execute(
                    sa.text("SELECT id FROM product_variants WHERE product_id=:pid AND display_name=:name"),
                    {"pid": product_id, "name": display_name},
                ).scalar_one()
        variant_ids[(product_id, display_name)] = variant_id

    for (product_id, display_name), variant_id in variant_ids.items():
        for table in ("price_records", "policy_prices", "st_rebates"):
            conn.execute(
                sa.text(f"UPDATE {table} SET variant_id=:vid WHERE product_id=:pid AND variant=:name"),
                {"vid": variant_id, "pid": product_id, "name": display_name},
            )


def downgrade():
    op.drop_index("ix_st_rebates_variant_id", table_name="st_rebates")
    op.drop_index("ix_policy_prices_variant_id", table_name="policy_prices")
    op.drop_index("ix_price_records_variant_id", table_name="price_records")
    op.drop_constraint("fk_st_rebates_variant_id", "st_rebates", type_="foreignkey")
    op.drop_constraint("fk_policy_prices_variant_id", "policy_prices", type_="foreignkey")
    op.drop_constraint("fk_price_records_variant_id", "price_records", type_="foreignkey")
    op.drop_column("st_rebates", "variant_id")
    op.drop_column("policy_prices", "variant_id")
    op.drop_column("price_records", "variant_id")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_table("product_variants")
