import sqlite3
from pathlib import Path


def get_database_path():
    from data_manager import get_active_database_path

    return get_active_database_path()


def get_database():
    database_path = get_database_path()

    if not database_path:
        return None

    return sqlite3.connect(
        database_path
    )


def get_tables(database_path=None):

    if database_path is None:
        database_path = get_database_path()

    if not database_path:
        return []

    conn = sqlite3.connect(
        database_path
    )

    try:

        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        return [
            row[0]
            for row in rows
        ]

    finally:

        conn.close()


def get_schema(database_path=None):

    if database_path is None:
        database_path = get_database_path()

    if not database_path:
        return ""

    conn = sqlite3.connect(
        database_path
    )

    try:

        parts = []

        for table in get_tables(
            database_path
        ):

            safe_table = (
                table
                .replace('"', '""')
            )

            columns = conn.execute(
                f'PRAGMA table_info("{safe_table}")'
            ).fetchall()

            parts.append(
                f'TABLE: "{table}"'
            )

            for column in columns:

                parts.append(
                    f'- "{column[1]}" '
                    f'({column[2]})'
                )

            parts.append("")

        return "\n".join(
            parts
        )

    finally:

        conn.close()