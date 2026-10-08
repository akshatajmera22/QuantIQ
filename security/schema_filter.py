from typing import Any, Dict, List, Tuple

from security.security_config import (
    is_table_blocked,
    is_column_blocked,
)


# ============================================================
# SCHEMA FILTER
# ============================================================
#
# This module removes protected database objects BEFORE the
# schema is sent to Gemini.
#
# Gemini therefore never receives:
#
# - blocked tables
# - blocked columns
# - relationships involving blocked tables
#
# ============================================================


def filter_schema_dict(
    schema: Any,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Filter a structured schema.

    Returns:

        filtered_schema,
        security_report
    """

    if not isinstance(schema, list):

        return (
            schema,
            {
                "blocked_tables": [],
                "blocked_columns": [],
            },
        )

    filtered_tables = []

    blocked_tables = []
    blocked_columns = []

    for table in schema:

        if not isinstance(table, dict):
            continue

        table_name = (
            table.get("table")
            or table.get("table_name")
            or table.get("name")
        )

        if not table_name:
            continue

        if is_table_blocked(table_name):

            blocked_tables.append(
                str(table_name)
            )

            continue

        filtered_table = dict(table)

        columns = (
            table.get("columns")
            or []
        )

        filtered_columns = []

        for column in columns:

            if not isinstance(column, dict):
                filtered_columns.append(
                    column
                )
                continue

            column_name = (
                column.get("name")
                or column.get("column_name")
            )

            if not column_name:

                filtered_columns.append(
                    column
                )

                continue

            if is_column_blocked(
                table_name,
                column_name,
            ):

                blocked_columns.append(
                    {
                        "table": str(
                            table_name
                        ),
                        "column": str(
                            column_name
                        ),
                    }
                )

                continue

            filtered_columns.append(
                column
            )

        filtered_table[
            "columns"
        ] = filtered_columns

        filtered_tables.append(
            filtered_table
        )

    filtered_schema = (
        filtered_tables
    )

    return (
        filtered_schema,
        {
            "blocked_tables":
                blocked_tables,
            "blocked_columns":
                blocked_columns,
        },
    )


# ============================================================
# TEXT SCHEMA FILTER
# ============================================================

def filter_schema_text(
    schema_text: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Filter planner-ready schema text.

    This handles common QuantIQ schema format:

        TABLE: "users"
        - "id" (int)
        - "password" (varchar)

    and removes protected tables/columns.
    """

    if not schema_text:
        return (
            schema_text,
            {
                "blocked_tables": [],
                "blocked_columns": [],
            },
        )

    lines = schema_text.splitlines()

    output = []

    blocked_tables = []
    blocked_columns = []

    current_table = None
    skip_current_table = False

    for line in lines:

        stripped = line.strip()

        # ----------------------------------------------------
        # TABLE HEADER
        # ----------------------------------------------------

        if stripped.upper().startswith(
            "TABLE:"
        ):

            table_name = (
                stripped[
                    stripped.upper().find(
                        "TABLE:"
                    )
                    + len("TABLE:")
                :]
                .strip()
                .strip('"')
                .strip("`")
            )

            current_table = table_name

            skip_current_table = (
                is_table_blocked(
                    table_name
                )
            )

            if skip_current_table:

                blocked_tables.append(
                    table_name
                )

                continue

            output.append(line)

            continue

        # ----------------------------------------------------
        # FOREIGN KEY RELATIONSHIPS
        # ----------------------------------------------------

        if stripped.upper().startswith(
            "FOREIGN KEY"
        ):

            # Relationships involving blocked tables should
            # not reach Gemini.
            if any(
                is_table_blocked(
                    part.strip(
                        ' "`'
                    )
                )
                for part in (
                    stripped
                    .replace(
                        "FOREIGN KEY RELATIONSHIPS:",
                        ""
                    )
                    .replace(
                        "->",
                        " "
                    )
                    .split()
                )
            ):

                continue

            output.append(line)

            continue

        # ----------------------------------------------------
        # COLUMN
        # ----------------------------------------------------

        if (
            current_table
            and stripped.startswith("-")
        ):

            column_part = (
                stripped[1:]
                .strip()
            )

            if column_part.startswith(
                '"'
            ):

                end_quote = (
                    column_part.find(
                        '"',
                        1
                    )
                )

                if end_quote > 1:

                    column_name = (
                        column_part[
                            1:end_quote
                        ]
                    )

                    if is_column_blocked(
                        current_table,
                        column_name,
                    ):

                        blocked_columns.append(
                            {
                                "table":
                                    current_table,
                                "column":
                                    column_name,
                            }
                        )

                        continue

            elif column_part.startswith(
                "`"
            ):

                end_quote = (
                    column_part.find(
                        "`",
                        1
                    )
                )

                if end_quote > 1:

                    column_name = (
                        column_part[
                            1:end_quote
                        ]
                    )

                    if is_column_blocked(
                        current_table,
                        column_name,
                    ):

                        blocked_columns.append(
                            {
                                "table":
                                    current_table,
                                "column":
                                    column_name,
                            }
                        )

                        continue

        # ----------------------------------------------------
        # NORMAL LINE
        # ----------------------------------------------------

        if not skip_current_table:
            output.append(line)

    return (
        "\n".join(output),
        {
            "blocked_tables":
                blocked_tables,
            "blocked_columns":
                blocked_columns,
        },
    )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def filter_schema_for_ai(
    schema_text: str,
) -> str:
    """
    Return only the AI-safe schema.
    """

    filtered, _ = filter_schema_text(
        schema_text
    )

    return filtered