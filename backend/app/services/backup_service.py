"""Portable single-user backups. Never include login hashes or job secrets."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import Date, DateTime, Numeric, insert, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import base  # noqa: F401
from app.db.base_class import Base

BACKUP_VERSION = 1


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def export_data(db):
    if db.bind.dialect.name == "postgresql":
        # All tables must describe the same instant, even if the scout edits
        # a note or removes a player while the export is being built.
        with db.bind.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with Session(bind=connection) as snapshot:
                return _export_snapshot(snapshot)
    return _export_snapshot(db)


def _export_snapshot(db):
    tables = {}
    for table in Base.metadata.sorted_tables:
        if table.name == "job_leases":
            continue
        columns = [c for c in table.columns if c.name != "hashed_password"]
        rows = [dict(row) for row in db.execute(select(*columns)).mappings()]
        tables[table.name] = rows
    return json.loads(json.dumps({"version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(), "tables": tables}, default=_json_value))


def restore_data(db, payload):
    """Restore into an empty, migrated database; never overwrite existing data."""
    if payload.get("version") != BACKUP_VERSION:
        raise ValueError("Versione backup non supportata")
    tables = [t for t in Base.metadata.sorted_tables if t.name != "job_leases"]
    if set(payload.get("tables", {})) != {t.name for t in tables}:
        raise ValueError("Backup incompleto o schema non compatibile")
    for table in tables:
        if db.execute(select(table).limit(1)).first() is not None:
            raise ValueError("Il ripristino richiede un database vuoto: nessun dato e' stato sovrascritto")
    users = payload["tables"]["users"]
    if len(users) > 1 or (users and not get_settings().AUTH_PASSWORD_HASH):
        raise ValueError("Ripristino single-user: configurare AUTH_PASSWORD_HASH")
    for table in tables:
        for original in payload["tables"][table.name]:
            row = dict(original)
            if table.name == "users":
                row["hashed_password"] = get_settings().AUTH_PASSWORD_HASH
                row["email"] = get_settings().AUTH_EMAIL
            for column in table.columns:
                value = row.get(column.name)
                if value is None:
                    continue
                if isinstance(column.type, DateTime):
                    row[column.name] = datetime.fromisoformat(value)
                elif isinstance(column.type, Date):
                    row[column.name] = date.fromisoformat(value)
                elif isinstance(column.type, Numeric):
                    row[column.name] = Decimal(str(value))
            db.execute(insert(table).values(**row))
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        for table in tables:
            if "id" in table.c:
                # Table names are static metadata, never taken from the backup.
                db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), "
                    f"EXISTS(SELECT 1 FROM {table.name}))"))
    db.commit()
