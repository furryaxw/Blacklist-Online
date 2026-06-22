"""Convert datetime columns to Unix timestamps.

Revision ID: 20260622_0001
Revises: None
Create Date: 2026-06-22 00:00:00

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIME_COLUMNS = {
    "user": ["created_at"],
    "apikey": ["created_at"],
    "blacklistentry": ["updated_at"],
    "whitelistentry": ["created_at"],
    "syncevent": ["created_at"],
    "application": ["created_at", "processed_at"],
    "operationlog": ["created_at"],
}


def upgrade(engine_name: str) -> None:
    globals()[f"upgrade_{engine_name}"]()


def downgrade(engine_name: str) -> None:
    globals()[f"downgrade_{engine_name}"]()


def upgrade_system() -> None:
    _upgrade_all_time_columns()


def downgrade_system() -> None:
    _downgrade_all_time_columns()


def upgrade_blacklist() -> None:
    _upgrade_all_time_columns()


def downgrade_blacklist() -> None:
    _downgrade_all_time_columns()


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(sa.text(f"PRAGMA table_info({_quote(table_name)})")).mappings().all()
    return {row["name"] for row in rows}


def _parse_timestamp(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def _format_datetime(value) -> str | None:
    ts = _parse_timestamp(value)
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None).isoformat(sep=" ")


def _rewrite_values(transform) -> None:
    connection = op.get_bind()
    for table_name, columns in TIME_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        if not existing_columns:
            continue

        quoted_table = _quote(table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                continue

            quoted_column = _quote(column_name)
            rows = connection.execute(
                sa.text(
                    f"SELECT rowid AS row_id, {quoted_column} AS value "
                    f"FROM {quoted_table} WHERE {quoted_column} IS NOT NULL"
                )
            ).mappings().all()

            for row in rows:
                converted = transform(row["value"])
                if converted is None:
                    continue
                connection.execute(
                    sa.text(
                        f"UPDATE {quoted_table} SET {quoted_column} = :value "
                        f"WHERE rowid = :row_id"
                    ),
                    {"value": converted, "row_id": row["row_id"]},
                )


def _alter_columns(type_) -> None:
    connection = op.get_bind()
    for table_name, columns in TIME_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        if not existing_columns:
            continue

        with op.batch_alter_table(table_name) as batch_op:
            for column_name in columns:
                if column_name in existing_columns:
                    batch_op.alter_column(column_name, type_=type_)


def _upgrade_all_time_columns() -> None:
    _rewrite_values(_parse_timestamp)
    _alter_columns(sa.Integer())


def _downgrade_all_time_columns() -> None:
    _rewrite_values(_format_datetime)
    _alter_columns(sa.DateTime())
