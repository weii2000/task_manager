import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from models import Base


def test_initial_migration_matches_orm_and_downgrades_cleanly() -> None:
    migration_path = next(
        Path("alembic/versions").glob("*_initial_planwise_schema.py")
    )
    spec = importlib.util.spec_from_file_location("initial_schema", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables)
        for table_name, table in Base.metadata.tables.items():
            assert {column["name"] for column in inspector.get_columns(table_name)} == {
                column.name for column in table.columns
            }

        with Operations.context(context):
            migration.downgrade()
        assert sa.inspect(connection).get_table_names() == []
