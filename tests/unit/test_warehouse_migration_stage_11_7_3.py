from pathlib import Path
from sqlalchemy import ForeignKey
from backend.app.db.base import Base
from backend.app.models.warehouse import Warehouse
from backend.app.models.storage_location import StorageLocation


def test_warehouse_registered():
    assert Base.metadata.tables["warehouses"] is Warehouse.__table__


def test_location_has_warehouse_fk():
    column = StorageLocation.__table__.c.warehouse_id
    assert not column.nullable
    assert any(isinstance(fk, ForeignKey) and fk.target_fullname == "warehouses.id" for fk in column.foreign_keys)


def test_warehouse_relation():
    assert "storage_locations" in Warehouse.__mapper__.relationships
    assert "warehouse" in StorageLocation.__mapper__.relationships


def test_migration_present():
    path = Path(__file__).resolve().parents[2] / "backend/alembic/versions/c71e4a9b203d_create_warehouses_and_assign_locations.py"
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "8b6d21a9c4f0"' in source
    assert 'def upgrade()' in source and 'def downgrade()' in source
