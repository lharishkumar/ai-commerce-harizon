"""Add customer display names."""
from alembic import op
import sqlalchemy as sa

revision = "0002_customer_display_name"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # 0001 creates from current SQLAlchemy metadata, so fresh installs may
    # already have the column. Existing databases still need the additive alter.
    inspector = sa.inspect(op.get_bind())
    if "display_name" not in {column["name"] for column in inspector.get_columns("customers")}: 
        op.add_column("customers", sa.Column("display_name", sa.String(length=120), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "display_name" in {column["name"] for column in inspector.get_columns("customers")}: 
        op.drop_column("customers", "display_name")
