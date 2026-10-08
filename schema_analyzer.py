"""
QuantIQ Schema Analyzer

Purpose:
    Understand an uploaded dataset without knowing its domain beforehand.

The analyzer identifies:
    - tables
    - columns
    - data types
    - sample values
    - likely column roles
    - numeric measures
    - dimensions
    - identifiers
    - dates
    - entities

IMPORTANT:
    This module does NOT contain dataset-specific mappings.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any


# ============================================================
# DATABASE HELPERS
# ============================================================

def quote_identifier(name: str) -> str:
    """
    Safely quote a SQLite identifier.
    """
    return '"' + str(name).replace('"', '""') + '"'


def get_connection(database_path: str):
    if not database_path:
        raise ValueError("Database path is required.")

    return sqlite3.connect(database_path)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_name(value: Any) -> str:
    """
    Normalize a column name for semantic comparison.

    Example:
        "Product Name" -> "productname"
        "product_name" -> "productname"
        "Product-ID"   -> "productid"
    """

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
    )


def humanize_name(value: Any) -> str:
    """
    Convert a column name into readable text.
    """

    text = str(value)

    text = text.replace("_", " ")
    text = text.replace("-", " ")

    text = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# TYPE DETECTION
# ============================================================

NUMERIC_TYPES = {
    "INTEGER",
    "INT",
    "BIGINT",
    "SMALLINT",
    "TINYINT",
    "REAL",
    "FLOAT",
    "DOUBLE",
    "DOUBLE PRECISION",
    "NUMERIC",
    "DECIMAL",
}

TEXT_TYPES = {
    "TEXT",
    "VARCHAR",
    "CHAR",
    "NCHAR",
    "NVARCHAR",
    "CLOB",
}

DATE_HINTS = {
    "date",
    "time",
    "timestamp",
    "year",
    "month",
    "day",
}


def is_numeric_type(data_type: str) -> bool:
    data_type = str(data_type).upper().strip()

    return (
        data_type in NUMERIC_TYPES
        or any(
            numeric_type in data_type
            for numeric_type in NUMERIC_TYPES
        )
    )


def is_text_type(data_type: str) -> bool:
    data_type = str(data_type).upper().strip()

    return (
        data_type in TEXT_TYPES
        or "CHAR" in data_type
        or "TEXT" in data_type
        or "CLOB" in data_type
    )


def looks_like_date_name(column_name: str) -> bool:
    normalized = normalize_name(column_name)

    return any(
        hint in normalized
        for hint in DATE_HINTS
    )


# ============================================================
# TABLE DISCOVERY
# ============================================================

def get_tables(database_path: str) -> list[str]:
    conn = get_connection(database_path)

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


# ============================================================
# COLUMN DISCOVERY
# ============================================================

def get_columns(
    database_path: str,
    table: str
) -> list[dict[str, Any]]:

    conn = get_connection(database_path)

    try:
        rows = conn.execute(
            f"""
            PRAGMA table_info(
                {quote_identifier(table)}
            )
            """
        ).fetchall()

        columns = []

        for row in rows:
            columns.append(
                {
                    "name": row[1],
                    "type": str(row[2]).upper(),
                    "not_null": bool(row[3]),
                    "primary_key": bool(row[5]),
                }
            )

        return columns

    finally:
        conn.close()


# ============================================================
# SAMPLE VALUES
# ============================================================

def get_sample_values(
    database_path: str,
    table: str,
    column: str,
    limit: int = 20
) -> list[Any]:

    conn = get_connection(database_path)

    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT
                {quote_identifier(column)}
            FROM {quote_identifier(table)}
            WHERE {quote_identifier(column)} IS NOT NULL
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [
            row[0]
            for row in rows
        ]

    except Exception:
        return []

    finally:
        conn.close()


# ============================================================
# COLUMN STATISTICS
# ============================================================

def get_column_statistics(
    database_path: str,
    table: str,
    column: str,
    data_type: str
) -> dict[str, Any]:

    conn = get_connection(database_path)

    try:

        safe_table = quote_identifier(table)
        safe_column = quote_identifier(column)

        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {safe_table}
            """
        ).fetchone()[0]

        non_null = conn.execute(
            f"""
            SELECT COUNT({safe_column})
            FROM {safe_table}
            """
        ).fetchone()[0]

        distinct = conn.execute(
            f"""
            SELECT COUNT(DISTINCT {safe_column})
            FROM {safe_table}
            """
        ).fetchone()[0]

        result = {
            "row_count": total,
            "non_null_count": non_null,
            "distinct_count": distinct,
            "null_count": max(
                total - non_null,
                0
            ),
            "distinct_ratio": (
                distinct / non_null
                if non_null
                else 0
            ),
        }

        if is_numeric_type(data_type):

            numeric = conn.execute(
                f"""
                SELECT
                    MIN({safe_column}),
                    MAX({safe_column}),
                    AVG({safe_column})
                FROM {safe_table}
                """
            ).fetchone()

            result["min"] = numeric[0]
            result["max"] = numeric[1]
            result["average"] = numeric[2]

        return result

    except Exception:
        return {
            "row_count": 0,
            "non_null_count": 0,
            "distinct_count": 0,
            "null_count": 0,
            "distinct_ratio": 0,
        }

    finally:
        conn.close()


# ============================================================
# ROLE DETECTION
# ============================================================

def detect_column_role(
    column: dict[str, Any]
) -> str:

    name = normalize_name(
        column["name"]
    )

    data_type = str(
        column["type"]
    ).upper()

    primary_key = column.get(
        "primary_key",
        False
    )

    statistics = column.get(
        "statistics",
        {}
    )

    distinct_ratio = statistics.get(
        "distinct_ratio",
        0
    )

    distinct_count = statistics.get(
        "distinct_count",
        0
    )

    row_count = statistics.get(
        "row_count",
        0
    )

    # --------------------------------------------------------
    # PRIMARY KEY
    # --------------------------------------------------------

    if primary_key:
        return "identifier"

    # --------------------------------------------------------
    # DATE / TIME
    # --------------------------------------------------------

    if looks_like_date_name(
        column["name"]
    ):
        return "date"

    # --------------------------------------------------------
    # NUMERIC
    # --------------------------------------------------------

    if is_numeric_type(data_type):

        # A column with almost every value unique
        # is often an identifier.
        if (
            row_count > 0
            and distinct_ratio >= 0.95
            and (
                name.endswith("id")
                or name == "id"
                or "code" in name
                or "number" in name
            )
        ):
            return "identifier"

        # Otherwise treat numeric fields as measures.
        return "measure"

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if is_text_type(data_type):

        # Strong identifier hints.
        if (
            name == "id"
            or name.endswith("id")
            or name.endswith("code")
            or "uuid" in name
        ):
            return "identifier"

        # Extremely high uniqueness often indicates
        # a record-level identifier.
        if (
            row_count > 0
            and distinct_ratio >= 0.98
            and distinct_count > 20
        ):
            return "identifier"

        return "dimension"

    return "unknown"


# ============================================================
# DATASET ANALYSIS
# ============================================================

def analyze_table(
    database_path: str,
    table: str
) -> dict[str, Any]:

    columns = get_columns(
        database_path,
        table
    )

    analyzed_columns = []

    for column in columns:

        statistics = get_column_statistics(
            database_path,
            table,
            column["name"],
            column["type"]
        )

        samples = get_sample_values(
            database_path,
            table,
            column["name"],
            limit=20
        )

        enriched = dict(column)

        enriched["display_name"] = (
            humanize_name(
                column["name"]
            )
        )

        enriched["statistics"] = (
            statistics
        )

        enriched["sample_values"] = (
            samples
        )

        enriched["role"] = (
            detect_column_role(
                enriched
            )
        )

        analyzed_columns.append(
            enriched
        )

    return {
        "table": table,
        "columns": analyzed_columns,
    }


def analyze_database(
    database_path: str
) -> dict[str, Any]:

    tables = get_tables(
        database_path
    )

    analyzed_tables = []

    for table in tables:

        analyzed_tables.append(
            analyze_table(
                database_path,
                table
            )
        )

    return {
        "tables": analyzed_tables
    }


# ============================================================
# COMPACT AI CONTEXT
# ============================================================

def build_ai_context(
    database_path: str
) -> str:
    """
    Build a compact description for Ollama.

    The AI receives actual database information,
    rather than relying on hardcoded dataset assumptions.
    """

    analysis = analyze_database(
        database_path
    )

    parts = []

    for table in analysis["tables"]:

        parts.append(
            f'TABLE: "{table["table"]}"'
        )

        for column in table["columns"]:

            samples = column.get(
                "sample_values",
                []
            )

            sample_text = ", ".join(
                str(value)
                for value in samples[:10]
            )

            parts.append(
                f'  COLUMN: "{column["name"]}"'
            )

            parts.append(
                f'    TYPE: {column["type"]}'
            )

            parts.append(
                f'    ROLE: {column["role"]}'
            )

            if sample_text:
                parts.append(
                    f'    SAMPLE VALUES: {sample_text}'
                )

            statistics = column.get(
                "statistics",
                {}
            )

            parts.append(
                "    DISTINCT VALUES: "
                + str(
                    statistics.get(
                        "distinct_count",
                        0
                    )
                )
            )

            parts.append("")

        parts.append("")

    return "\n".join(parts)


# ============================================================
# SIMPLE API
# ============================================================

def get_dataset_analysis(
    database_path: str
) -> dict[str, Any]:

    return analyze_database(
        database_path
    )


def get_ai_context(
    database_path: str
) -> str:

    return build_ai_context(
        database_path
    )