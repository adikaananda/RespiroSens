"""
Zero-downtime, zero-dependency schema sync for this project's small SQLite/
MySQL database (there is no Alembic/Flask-Migrate here — see requirements.txt).

`sync_schema(app)` is called once at app startup (see app/__init__.py). It:
  1. Creates any tables that don't exist yet (safe: db.create_all() never
     touches existing tables), so a brand new install works with zero manual
     steps beyond `python init_db.py`.
  2. Adds any *new* columns that a model defines but an existing database
     file predates (e.g. `patients.age`, `patients.height_cm`,
     `patients.weight_kg`) via `ALTER TABLE ... ADD COLUMN`, so upgrading an
     existing RespiroSens install never requires deleting the database.

This intentionally does NOT drop or alter existing columns — it only adds
columns that are missing, which is safe on both SQLite and MySQL.
"""

from sqlalchemy import inspect, text

from app.extensions import db

# Maps SQLAlchemy column types -> a portable SQL type usable in a bare
# ALTER TABLE ADD COLUMN on both SQLite and MySQL.
_SQL_TYPE = {
    "INTEGER": "INTEGER",
    "FLOAT": "FLOAT",
    "BOOLEAN": "BOOLEAN",
    "VARCHAR": "VARCHAR(255)",
    "TEXT": "TEXT",
    "DATE": "DATE",
    "DATETIME": "DATETIME",
    "JSON": "TEXT",
}


def _portable_type(column):
    type_name = column.type.__class__.__name__.upper()
    return _SQL_TYPE.get(type_name, "TEXT")


def sync_schema(app):
    with app.app_context():
        db.create_all()

        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        for model in db.Model.registry.mappers:
            table = model.local_table
            if table.name not in existing_tables:
                continue  # brand new table — db.create_all() above already made it
            existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {_portable_type(column)}"
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text(ddl))
                    app.logger.info("schema_sync: added missing column %s.%s", table.name, column.name)
                except Exception as exc:  # pragma: no cover - defensive, don't crash startup
                    app.logger.warning("schema_sync: could not add %s.%s (%s)", table.name, column.name, exc)
