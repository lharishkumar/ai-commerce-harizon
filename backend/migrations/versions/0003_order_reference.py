"""Add short numeric order references."""
from alembic import op
import sqlalchemy as sa

revision = "0003_order_reference"
down_revision = "0002_customer_display_name"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "order_reference" not in columns:
        op.add_column("orders", sa.Column("order_reference", sa.String(length=12), nullable=True))

    rows = bind.execute(sa.text("SELECT id FROM orders WHERE order_reference IS NULL ORDER BY created_at, id")).fetchall()
    for index, (order_id,) in enumerate(rows, start=100001):
        bind.execute(sa.text("UPDATE orders SET order_reference = :reference WHERE id = :order_id"),
                     {"reference": str(index), "order_id": order_id})

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("orders")}
    if "ix_orders_order_reference" not in indexes:
        op.create_index("ix_orders_order_reference", "orders", ["order_reference"], unique=True)
    op.alter_column("orders", "order_reference", existing_type=sa.String(length=12), nullable=False)


def downgrade():
    op.drop_index("ix_orders_order_reference", table_name="orders")
    op.drop_column("orders", "order_reference")
