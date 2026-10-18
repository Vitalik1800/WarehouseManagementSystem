"""Create warehouses and assign existing storage locations to MAIN.

Revision ID: c71e4a9b203d
Revises: 8b6d21a9c4f0
"""
from alembic import op
import sqlalchemy as sa

revision = "c71e4a9b203d"
down_revision = "8b6d21a9c4f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name=op.f("uq_warehouses_name")),
        sa.UniqueConstraint("code", name=op.f("uq_warehouses_code")),
    )
    op.add_column("storage_locations", sa.Column("warehouse_id", sa.Integer(), nullable=True))
    connection = op.get_bind()
    result = connection.execute(
        sa.text("INSERT INTO warehouses (name, code, description, is_active) "
                "VALUES (:name, :code, :description, :active)"),
        {"name": "Основний склад", "code": "MAIN", "description": "Склад для наявних місць зберігання", "active": True},
    )
    warehouse_id = result.lastrowid
    if warehouse_id is None:
        warehouse_id = connection.execute(sa.text("SELECT id FROM warehouses WHERE code = 'MAIN'")).scalar_one()
    connection.execute(
        sa.text("UPDATE storage_locations SET warehouse_id = :warehouse_id WHERE warehouse_id IS NULL"),
        {"warehouse_id": warehouse_id},
    )
    op.alter_column("storage_locations", "warehouse_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        op.f("fk_storage_locations_warehouse_id_warehouses"),
        "storage_locations", "warehouses", ["warehouse_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_storage_locations_warehouse_id", "storage_locations", ["warehouse_id"])
    # Keep existing global name uniqueness until the service and API are updated.


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(sa.text("SELECT COUNT(*) FROM warehouses")).scalar_one()
    if count != 1:
        raise RuntimeError("Downgrade blocked: multiple warehouses exist; back up and consolidate first")
    op.drop_index("ix_storage_locations_warehouse_id", table_name="storage_locations")
    op.drop_constraint(op.f("fk_storage_locations_warehouse_id_warehouses"), "storage_locations", type_="foreignkey")
    op.drop_column("storage_locations", "warehouse_id")
    op.drop_table("warehouses")
