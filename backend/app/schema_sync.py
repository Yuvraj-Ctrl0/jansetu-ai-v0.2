"""Additive schema sync for existing databases.

`db.create_all()` creates missing tables but never adds new columns to tables that
already exist. This helper adds any model column that is missing from the live table
(MySQL, PostgreSQL or SQLite). It ONLY runs `ALTER TABLE ... ADD COLUMN` for nullable
columns — it never drops, renames or changes existing columns or data.
For production, prefer proper migrations (Alembic) and back up first.
"""
from sqlalchemy import inspect, text

from .extensions import db


def sync_schema(verbose=True):
    engine = db.engine
    inspector = inspect(engine)
    preparer = engine.dialect.identifier_preparer
    existing_tables = set(inspector.get_table_names())
    added = []
    with engine.begin() as connection:
        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all() handles brand-new tables
            live_columns = {c['name'] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_columns:
                    continue
                if not column.nullable:
                    if verbose:
                        print(f'Skipped non-nullable column {table.name}.{column.name}: add it with a migration')
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                connection.execute(text(
                    f'ALTER TABLE {preparer.quote(table.name)} ADD COLUMN {preparer.quote(column.name)} {column_type}'
                ))
                added.append(f'{table.name}.{column.name}')
                if verbose:
                    print(f'Added column {table.name}.{column.name} ({column_type})')
    if verbose and not added:
        print('Schema already up to date.')
    return added
