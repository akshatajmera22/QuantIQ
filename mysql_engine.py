"""
QuantIQ MySQL Engine

Purpose:
    Provides a safe, controlled interface to live MySQL databases.

Responsibilities:
    - Connect to MySQL
    - Test connections
    - List databases
    - List tables
    - Inspect table schemas
    - Inspect foreign-key relationships
    - Retrieve sample categorical values
    - Execute read-only SQL queries
    - Convert results to JSON-safe Python objects

Important:
    This module never sends database credentials to Gemini.
    Gemini only receives schema/context information and query results.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import Error


# ============================================================
# CONNECTION
# ============================================================

def create_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
    connect_timeout: int = 10,
):
    """
    Create a MySQL connection.

    The connection is created only when explicitly requested.
    Credentials are never returned by this module.
    """

    if not host:
        raise ValueError(
            "MySQL host is required."
        )

    if not username:
        raise ValueError(
            "MySQL username is required."
        )

    if not isinstance(port, int):
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise ValueError(
                "MySQL port must be an integer."
            )

    if port < 1 or port > 65535:
        raise ValueError(
            "MySQL port must be between 1 and 65535."
        )

    config = {
        "host": host.strip(),
        "port": port,
        "user": username.strip(),
        "password": password or "",
        "connection_timeout": connect_timeout,
        "autocommit": True,
    }

    if database:
        config["database"] = database.strip()

    return mysql.connector.connect(
        **config
    )


# ============================================================
# TEST CONNECTION
# ============================================================

def test_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Test a MySQL connection and return safe connection metadata.

    Passwords are never included in the returned response.
    """

    conn = None

    try:
        conn = create_connection(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                DATABASE(),
                VERSION(),
                USER()
            """
        )

        row = cursor.fetchone()

        current_database = (
            row[0]
            if row
            else database
        )

        version = (
            row[1]
            if row
            else None
        )

        server_user = (
            row[2]
            if row
            else None
        )

        cursor.close()

        return {
            "success": True,
            "connected": True,
            "host": host,
            "port": port,
            "database": current_database,
            "server_version": version,
            "server_user": server_user,
            "message": "MySQL connection successful.",
        }

    except Error as exc:

        return {
            "success": False,
            "connected": False,
            "host": host,
            "port": port,
            "database": database,
            "message": clean_mysql_error(exc),
        }

    finally:

        if (
            conn is not None
            and conn.is_connected()
        ):
            conn.close()


# ============================================================
# DATABASES
# ============================================================

def list_databases(
    connection,
) -> List[str]:
    """
    Return databases visible to the connected MySQL user.
    """

    cursor = connection.cursor()

    try:

        cursor.execute(
            "SHOW DATABASES"
        )

        databases = []

        for row in cursor.fetchall():

            if row and row[0]:

                databases.append(
                    str(row[0])
                )

        return databases

    finally:

        cursor.close()


# ============================================================
# TABLES
# ============================================================

def list_tables(
    connection,
    database: Optional[str] = None,
) -> List[str]:
    """
    Return tables from the selected database.

    Uses INFORMATION_SCHEMA.
    """

    if database is None:

        cursor = connection.cursor()

        try:

            cursor.execute(
                "SELECT DATABASE()"
            )

            row = cursor.fetchone()

            database = (
                row[0]
                if row
                else None
            )

        finally:

            cursor.close()

    if not database:

        raise ValueError(
            "No MySQL database is selected."
        )

    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """,
            (database,),
        )

        return [
            str(row[0])
            for row in cursor.fetchall()
            if row and row[0]
        ]

    finally:

        cursor.close()


# ============================================================
# SCHEMA
# ============================================================

def get_schema(
    connection,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return structured schema information for all tables.

    Includes:
        - table names
        - column names
        - data types
        - nullable
        - primary key
        - default values
        - extra metadata
    """

    if database is None:

        cursor = connection.cursor()

        try:

            cursor.execute(
                "SELECT DATABASE()"
            )

            row = cursor.fetchone()

            database = (
                row[0]
                if row
                else None
            )

        finally:

            cursor.close()

    if not database:

        raise ValueError(
            "No MySQL database is selected."
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_DEFAULT,
                EXTRA,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY
                TABLE_NAME,
                ORDINAL_POSITION
            """,
            (database,),
        )

        rows = cursor.fetchall()

        tables: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for row in rows:

            table_name = (
                row["TABLE_NAME"]
            )

            if table_name not in tables:

                tables[table_name] = {
                    "table_name":
                        table_name,
                    "columns": [],
                }

            tables[
                table_name
            ][
                "columns"
            ].append(
                {
                    "name":
                        row["COLUMN_NAME"],

                    "data_type":
                        row["DATA_TYPE"],

                    "column_type":
                        row["COLUMN_TYPE"],

                    "nullable":
                        row["IS_NULLABLE"]
                        == "YES",

                    "primary_key":
                        row["COLUMN_KEY"]
                        == "PRI",

                    "default":
                        row["COLUMN_DEFAULT"],

                    "extra":
                        row["EXTRA"],

                    "ordinal_position":
                        row[
                            "ORDINAL_POSITION"
                        ],
                }
            )

        return {
            "database": database,
            "tables": list(
                tables.values()
            ),
        }

    finally:

        cursor.close()


# ============================================================
# FOREIGN KEY RELATIONSHIPS
# ============================================================

def get_foreign_keys(
    connection,
    database: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return foreign-key relationships for the selected database.

    Example:

        payment.customer_id
            ->
        customer.customer_id

    This metadata contains schema information only.
    No credentials or row data are returned.
    """

    if database is None:

        cursor = connection.cursor()

        try:

            cursor.execute(
                "SELECT DATABASE()"
            )

            row = cursor.fetchone()

            database = (
                row[0]
                if row
                else None
            )

        finally:

            cursor.close()

    if not database:

        raise ValueError(
            "No MySQL database is selected."
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME,
                CONSTRAINT_NAME,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
              AND REFERENCED_COLUMN_NAME IS NOT NULL
            ORDER BY
                TABLE_NAME,
                CONSTRAINT_NAME,
                ORDINAL_POSITION
            """,
            (
                database,
                database,
            ),
        )

        relationships = []

        for row in cursor.fetchall():

            relationships.append(
                {
                    "table":
                        row["TABLE_NAME"],

                    "column":
                        row["COLUMN_NAME"],

                    "referenced_table":
                        row[
                            "REFERENCED_TABLE_NAME"
                        ],

                    "referenced_column":
                        row[
                            "REFERENCED_COLUMN_NAME"
                        ],

                    "constraint":
                        row[
                            "CONSTRAINT_NAME"
                        ],

                    "ordinal_position":
                        row[
                            "ORDINAL_POSITION"
                        ],
                }
            )

        return relationships

    finally:

        cursor.close()


# ============================================================
# SCHEMA TEXT FOR GEMINI
# ============================================================

def build_schema_context(
    connection,
    database: Optional[str] = None,
) -> str:
    """
    Convert MySQL schema and foreign-key relationships into
    compact planner context.

    Credentials are never included.
    """

    schema = get_schema(
        connection=connection,
        database=database,
    )

    relationships = get_foreign_keys(
        connection=connection,
        database=schema["database"],
    )

    parts = []

    parts.append(
        f"DATABASE: {schema['database']}"
    )

    parts.append(
        "DIALECT: MySQL"
    )

    parts.append("")

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    for table in schema["tables"]:

        parts.append(
            f'TABLE: "{table["table_name"]}"'
        )

        for column in table["columns"]:

            flags = []

            if column["primary_key"]:

                flags.append(
                    "PRIMARY KEY"
                )

            if not column["nullable"]:

                flags.append(
                    "NOT NULL"
                )

            flag_text = ""

            if flags:

                flag_text = (
                    " ["
                    +
                    ", ".join(flags)
                    +
                    "]"
                )

            parts.append(
                f'- "{column["name"]}" '
                f'({column["column_type"]})'
                f'{flag_text}'
            )

        parts.append("")

    # --------------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------------

    parts.append(
        "FOREIGN KEY RELATIONSHIPS:"
    )

    if relationships:

        for relationship in relationships:

            parts.append(
                f'- "{relationship["table"]}".'
                f'"{relationship["column"]}" '
                f'-> '
                f'"{relationship["referenced_table"]}".'
                f'"{relationship["referenced_column"]}"'
            )

    else:

        parts.append(
            "- None detected"
        )

    return "\n".join(parts)


# ============================================================
# SAMPLE VALUES
# ============================================================

def get_database_values(
    connection,
    database: Optional[str] = None,
    limit_per_column: int = 100,
) -> Dict[
    str,
    Dict[str, List[str]]
]:
    """
    Retrieve sample distinct values for categorical columns.

    This is intentionally limited to avoid sending huge amounts
    of database data to the LLM.
    """

    schema = get_schema(
        connection=connection,
        database=database,
    )

    result = {}

    cursor = connection.cursor()

    try:

        for table in schema["tables"]:

            table_name = (
                table["table_name"]
            )

            result[
                table_name
            ] = {}

            for column in table["columns"]:

                data_type = str(
                    column["data_type"]
                ).lower()

                categorical_types = {
                    "char",
                    "varchar",
                    "text",
                    "tinytext",
                    "mediumtext",
                    "longtext",
                    "enum",
                    "set",
                }

                if (
                    data_type
                    not in categorical_types
                ):
                    continue

                column_name = (
                    column["name"]
                )

                safe_table = quote_identifier(
                    table_name
                )

                safe_column = quote_identifier(
                    column_name
                )

                sql = (
                    f"SELECT DISTINCT "
                    f"{safe_column} "
                    f"FROM {safe_table} "
                    f"WHERE {safe_column} "
                    f"IS NOT NULL "
                    f"LIMIT %s"
                )

                try:

                    cursor.execute(
                        sql,
                        (
                            limit_per_column,
                        ),
                    )

                    values = []

                    for row in cursor.fetchall():

                        if not row:
                            continue

                        value = row[0]

                        if value is None:
                            continue

                        value = str(
                            value
                        ).strip()

                        if value:

                            values.append(
                                value
                            )

                    result[
                        table_name
                    ][
                        column_name
                    ] = values

                except Error:

                    # One problematic column should not
                    # prevent the entire schema from loading.
                    continue

        return result

    finally:

        cursor.close()


# ============================================================
# READ-ONLY SQL EXECUTION
# ============================================================

def execute_query(
    connection,
    sql: str,
) -> Dict[str, Any]:
    """
    Execute a single read-only SQL query.

    Only SELECT / WITH queries are permitted.
    """

    if not isinstance(
        sql,
        str,
    ):

        raise ValueError(
            "SQL must be a string."
        )

    sql = sql.strip()

    if not sql:

        raise ValueError(
            "SQL query cannot be empty."
        )

    validate_read_only_sql(
        sql
    )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            sql
        )

        rows = cursor.fetchall()

        safe_rows = [
            make_json_safe(row)
            for row in rows
        ]

        columns = (
            [
                column[0]
                for column in cursor.description
            ]
            if cursor.description
            else []
        )

        return {
            "success": True,
            "columns": columns,
            "rows": safe_rows,
            "row_count":
                len(safe_rows),
        }

    finally:

        cursor.close()


# ============================================================
# READ-ONLY SQL VALIDATION
# ============================================================

def validate_read_only_sql(
    sql: str,
):
    """
    Reject SQL that can modify the database.

    QuantIQ's natural-language analyst should only read data.
    """

    normalized = (
        sql.strip()
        .lower()
    )

    normalized = (
        normalized
        .rstrip(";")
        .strip()
    )

    allowed_prefixes = (
        "select ",
        "select\n",
        "with ",
        "with\n",
    )

    if not normalized.startswith(
        allowed_prefixes
    ):

        raise ValueError(
            "Only read-only SELECT queries are allowed."
        )

    forbidden_keywords = (
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "truncate ",
        "create ",
        "replace ",
        "grant ",
        "revoke ",
        "rename ",
        "set ",
        "call ",
        "load ",
        "outfile ",
        "dumpfile ",
    )

    for keyword in forbidden_keywords:

        if keyword in normalized:

            raise ValueError(
                "Unsafe SQL operation detected."
            )


# ============================================================
# IDENTIFIER QUOTING
# ============================================================

def quote_identifier(
    name: str,
) -> str:
    """
    Safely quote a MySQL identifier using backticks.
    """

    if not isinstance(
        name,
        str,
    ):

        raise ValueError(
            "SQL identifier must be a string."
        )

    name = name.strip()

    if not name:

        raise ValueError(
            "SQL identifier cannot be empty."
        )

    if "\x00" in name:

        raise ValueError(
            "Invalid null character in identifier."
        )

    name = name.replace(
        "`",
        "``",
    )

    return f"`{name}`"


# ============================================================
# JSON SAFE VALUES
# ============================================================

def make_json_safe(
    value: Any,
) -> Any:
    """
    Convert MySQL/Python values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value

    if isinstance(
        value,
        Decimal,
    ):

        return float(
            value
        )

    if isinstance(
        value,
        (
            datetime,
            date,
            time,
        ),
    ):

        return value.isoformat()

    if isinstance(
        value,
        bytes,
    ):

        return value.decode(
            "utf-8",
            errors="replace",
        )

    if isinstance(
        value,
        list,
    ):

        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        tuple,
    ):

        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key):
                make_json_safe(
                    val
                )
            for key, val
            in value.items()
        }

    return str(
        value
    )


# ============================================================
# ERROR CLEANING
# ============================================================

def clean_mysql_error(
    error: Exception,
) -> str:
    """
    Convert MySQL connector errors into user-friendly messages.

    Avoid exposing passwords or full connection strings.
    """

    message = str(
        error
    )

    sensitive_patterns = (
        "password",
        "passwd",
    )

    for pattern in sensitive_patterns:

        if (
            pattern.lower()
            in message.lower()
        ):

            return (
                "MySQL connection failed. "
                "Please verify the connection credentials."
            )

    return message