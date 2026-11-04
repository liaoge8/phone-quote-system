"""Initial immutable price archive schema."""
from alembic import op
import sqlalchemy as sa
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('username', sa.String(64), nullable=False, unique=True), sa.Column('password_hash', sa.String(255), nullable=False), sa.Column('role', sa.String(16), nullable=False, server_default='member'), sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column('token_epoch', sa.Integer(), nullable=False, server_default='0'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_table('products', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('brand', sa.String(40), nullable=False), sa.Column('model', sa.String(100), nullable=False), sa.Column('intro', sa.Text()), sa.Column('status', sa.String(20), nullable=False, server_default='on_sale'), sa.Column('archived_at', sa.DateTime(timezone=True)), sa.Column('archived_by', sa.Integer()), sa.Column('archive_reason', sa.Text()), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_products_brand', 'products', ['brand'])
    op.create_index('ix_products_model', 'products', ['model'])
    op.create_table('price_records', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False), sa.Column('variant', sa.String(100), nullable=False), sa.Column('price_type', sa.String(32), nullable=False), sa.Column('price', sa.Numeric(12, 2), nullable=False), sa.Column('effective_date', sa.Date(), nullable=False), sa.Column('note', sa.Text()), sa.Column('recorded_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('voided_at', sa.DateTime(timezone=True)), sa.Column('voided_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT')), sa.Column('void_reason', sa.Text()))
    op.create_index('ix_price_records_product_id', 'price_records', ['product_id'])
    op.create_index('ix_price_records_effective_date', 'price_records', ['effective_date'])
    op.create_table('audit_logs', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT')), sa.Column('action', sa.String(64), nullable=False), sa.Column('target_type', sa.String(64)), sa.Column('target_id', sa.String(64)), sa.Column('detail', sa.JSON()), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])

def downgrade():
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index('ix_price_records_effective_date', table_name='price_records')
    op.drop_index('ix_price_records_product_id', table_name='price_records')
    op.drop_table('price_records')
    op.drop_index('ix_products_model', table_name='products')
    op.drop_index('ix_products_brand', table_name='products')
    op.drop_table('products')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
