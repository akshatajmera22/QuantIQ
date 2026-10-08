"""
QuantIQ MySQL Connection Manager

Maintains the active MySQL connection configuration for the
current backend process.

Important:
    Passwords are kept only in server memory and are never
    returned through API responses.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mysql_engine import (
    create_connection,
    test_connection,
)


# ============================================================
# ACTIVE CONNECTION STATE
# ============================================================

_active_connection = None

_active_config: Optional[Dict[str, Any]] = None


# ============================================================
# CONNECT
# ============================================================

def connect_mysql(
    host: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connect to MySQL and make it the active data source.
    """

    global _active_connection
    global _active_config

    disconnect_mysql()

    connection = create_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )

    if not connection.is_connected():
        raise RuntimeError(
            "MySQL connection could not be established."
        )

    _active_connection = connection

    _active_config = {
        "host": host,
        "port": int(port),
        "username": username,
        "database": database,
        "password": password,
    }

    return get_active_connection_info()


# ============================================================
# TEST CONNECTION
# ============================================================

def test_mysql_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Test a MySQL connection without making it the active
    connection.
    """

    return test_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )


# ============================================================
# TEST + CONNECT
# ============================================================

def test_and_connect_mysql(
    host: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Test the connection first.

    Only establish active state when the test succeeds.
    """

    result = test_mysql_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )

    if not result.get("success"):
        return result

    try:

        info = connect_mysql(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

        return {
            "success": True,
            "connected": True,
            **info,
        }

    except Exception as exc:

        disconnect_mysql()

        return {
            "success": False,
            "connected": False,
            "message": str(exc),
        }


# ============================================================
# ACTIVE CONNECTION
# ============================================================

def get_mysql_connection():
    """
    Return the active MySQL connection.

    Raises an error if no active MySQL connection exists.
    """

    global _active_connection

    if (
        _active_connection is None
        or not _active_connection.is_connected()
    ):
        raise RuntimeError(
            "No active MySQL connection."
        )

    return _active_connection


# ============================================================
# ACTIVE DATABASE NAME
# ============================================================

def get_mysql_database_name():
    """
    Return the currently selected MySQL database name.
    """

    if not _active_config:
        return None

    return _active_config.get(
        "database"
    )


# ============================================================
# DATABASE VALUES
# ============================================================

def get_mysql_database_values(
    connection=None,
    database: Optional[str] = None,
    limit_per_column: int = 100,
):
    """
    Return useful categorical values from the active MySQL
    database.

    Only text-like columns are inspected.
    """

    if connection is None:
        connection = get_mysql_connection()

    if database is None:
        database = get_mysql_database_name()

    if not database:
        raise RuntimeError(
            "No MySQL database is selected."
        )

    if limit_per_column < 1:
        limit_per_column = 1

    cursor = connection.cursor()

    try:

        # ----------------------------------------------------
        # GET TABLES
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                TABLE_NAME
            FROM
                INFORMATION_SCHEMA.TABLES
            WHERE
                TABLE_SCHEMA = %s
                AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY
                TABLE_NAME
            """,
            (database,),
        )

        table_rows = cursor.fetchall()

        table_names = []

        for row in table_rows:

            if isinstance(row, dict):
                table_names.append(
                    row["TABLE_NAME"]
                )
            else:
                table_names.append(
                    row[0]
                )

        output = {}

        # ----------------------------------------------------
        # PROCESS TABLES
        # ----------------------------------------------------

        for table_name in table_names:

            try:

                cursor.execute(
                    """
                    SELECT
                        COLUMN_NAME,
                        DATA_TYPE
                    FROM
                        INFORMATION_SCHEMA.COLUMNS
                    WHERE
                        TABLE_SCHEMA = %s
                        AND TABLE_NAME = %s
                    ORDER BY
                        ORDINAL_POSITION
                    """,
                    (
                        database,
                        table_name,
                    ),
                )

                column_rows = cursor.fetchall()

                table_values = {}

                for column_row in column_rows:

                    if isinstance(
                        column_row,
                        dict,
                    ):

                        column_name = column_row[
                            "COLUMN_NAME"
                        ]

                        data_type = str(
                            column_row[
                                "DATA_TYPE"
                            ]
                        ).lower()

                    else:

                        column_name = column_row[0]

                        data_type = str(
                            column_row[1]
                        ).lower()

                    # ------------------------------------------------
                    # Only inspect text/categorical columns.
                    # ------------------------------------------------

                    if data_type not in {
                        "char",
                        "varchar",
                        "text",
                        "tinytext",
                        "mediumtext",
                        "longtext",
                        "enum",
                        "set",
                    }:
                        continue

                    escaped_table = (
                        str(table_name)
                        .replace("`", "``")
                    )

                    escaped_column = (
                        str(column_name)
                        .replace("`", "``")
                    )

                    sql = f"""
                        SELECT DISTINCT
                            `{escaped_column}`
                        FROM
                            `{escaped_table}`
                        WHERE
                            `{escaped_column}` IS NOT NULL
                        ORDER BY
                            `{escaped_column}`
                        LIMIT {int(limit_per_column)}
                    """

                    try:

                        cursor.execute(sql)

                        value_rows = cursor.fetchall()

                    except Exception:

                        continue

                    values = []

                    for value_row in value_rows:

                        if isinstance(
                            value_row,
                            dict,
                        ):

                            value = next(
                                iter(
                                    value_row.values()
                                )
                            )

                        else:

                            value = value_row[0]

                        if value is None:
                            continue

                        values.append(value)

                    if values:

                        table_values[
                            str(column_name)
                        ] = values

                if table_values:

                    output[
                        str(table_name)
                    ] = table_values

            except Exception:

                continue

        return output

    finally:

        cursor.close()


# ============================================================
# CONNECTION STATUS
# ============================================================

def is_mysql_connected() -> bool:

    return (
        _active_connection is not None
        and _active_connection.is_connected()
    )


# ============================================================
# ACTIVE INFO
# ============================================================

def get_active_connection_info():
    """
    Return safe metadata.

    Password is deliberately excluded.
    """

    if not _active_config:
        return {
            "connected": False,
            "host": None,
            "port": None,
            "username": None,
            "database": None,
        }

    return {
        "connected": is_mysql_connected(),
        "host": _active_config.get("host"),
        "port": _active_config.get("port"),
        "username": _active_config.get("username"),
        "database": _active_config.get("database"),
    }


# ============================================================
# INTERNAL CONFIG
# ============================================================

def get_active_mysql_config():
    """
    Internal use only.

    Returns the active configuration including the password.

    Never expose this object through an API response.
    """

    if not _active_config:
        raise RuntimeError(
            "No active MySQL connection."
        )

    return dict(
        _active_config
    )


# ============================================================
# SELECT DATABASE
# ============================================================

def select_mysql_database(
    database: str,
) -> Dict[str, Any]:
    """
    Switch the active MySQL connection to another database.
    """

    global _active_config

    if not database:
        raise ValueError(
            "Database name is required."
        )

    connection = get_mysql_connection()

    escaped_database = (
        database.replace("`", "``")
    )

    cursor = connection.cursor()

    try:

        cursor.execute(
            f"USE `{escaped_database}`"
        )

    finally:

        cursor.close()

    if _active_config is None:
        _active_config = {}

    _active_config[
        "database"
    ] = database

    return get_active_connection_info()


# ============================================================
# LIST DATABASES
# ============================================================

def list_mysql_databases(
    connection=None,
):
    """
    Return databases available to the connected MySQL user.
    """

    if connection is None:
        connection = get_mysql_connection()

    cursor = connection.cursor()

    try:

        cursor.execute(
            "SHOW DATABASES"
        )

        rows = cursor.fetchall()

        databases = []

        for row in rows:

            if isinstance(row, dict):

                value = next(
                    iter(row.values())
                )

            else:

                value = row[0]

            databases.append(
                str(value)
            )

        return databases

    finally:

        cursor.close()


# ============================================================
# DISCONNECT
# ============================================================

def disconnect_mysql():

    global _active_connection
    global _active_config

    if _active_connection is not None:

        try:

            if _active_connection.is_connected():
                _active_connection.close()

        except Exception:
            pass

    _active_connection = None
    _active_config = None