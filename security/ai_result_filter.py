# ============================================================
# QUANTIQ AI RESULT FILTER
# ============================================================
#
# Database
#     ↓
# SQL validation
#     ↓
# Execute query
#     ↓
# AI RESULT FILTER  ← THIS FILE
#     ↓
# Safe result
#     ↓
# Gemini
#
# IMPORTANT:
#
# The frontend/UI result is NOT modified.
#
# This module creates a separate copy specifically for Gemini.
# ============================================================


from typing import Any, Dict, List, Tuple

from security.security_config import (
    is_table_blocked,
    is_column_blocked,
)

from security.ai_data_policy import (
    ALLOW_AGGREGATE_RESULTS,
    ALLOW_RAW_ROWS,
    BLOCK_SENSITIVE_COLUMNS,
    MAX_AI_ROWS,
    MAX_AI_COLUMNS,
    MAX_AI_RESULT_CHARACTERS,
)


# ============================================================
# HELPERS
# ============================================================

def _normalize(value: Any) -> str:
    """
    Normalize an identifier for security comparisons.
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .strip("`")
        .strip('"')
        .strip("[")
        .strip("]")
        .lower()
    )


def _is_sensitive_column(
    column_name: str,
    table_name: str = "",
) -> bool:
    """
    Check whether a result column should be blocked.
    """

    if not BLOCK_SENSITIVE_COLUMNS:
        return False

    return is_column_blocked(
        table_name,
        column_name,
    )


def _get_result_tables(
    query_plan: Any,
) -> List[str]:
    """
    Extract tables associated with the query plan.

    The planner's table information is treated only as
    security metadata here.
    """

    if not isinstance(query_plan, dict):
        return []

    tables = query_plan.get(
        "tables",
        [],
    )

    if not isinstance(tables, list):
        return []

    result = []

    for table in tables:

        if isinstance(table, dict):

            name = (
                table.get("table")
                or table.get("table_name")
                or table.get("name")
            )

        else:

            name = table

        if name:
            result.append(
                str(name)
            )

    return result


def _has_aggregate_analysis(
    query_plan: Any,
) -> bool:
    """
    Determine whether the query plan represents an
    aggregate/KPI-style result.

    This deliberately relies on planner structure rather
    than hardcoding dataset-specific column names.
    """

    if not isinstance(query_plan, dict):
        return False

    aggregation = query_plan.get(
        "aggregation"
    )

    if aggregation:
        return True

    intent = str(
        query_plan.get(
            "intent",
            ""
        )
    ).lower()

    aggregate_intents = {
        "aggregation",
        "aggregate",
        "kpi",
        "summary",
        "comparison",
        "trend",
        "ranking",
        "analysis",
    }

    if intent in aggregate_intents:
        return True

    analyses = query_plan.get(
        "analyses",
        []
    )

    if isinstance(analyses, list):

        for analysis in analyses:

            if not isinstance(
                analysis,
                dict,
            ):
                continue

            if analysis.get(
                "aggregation"
            ):
                return True

            analysis_intent = str(
                analysis.get(
                    "intent",
                    ""
                )
            ).lower()

            if analysis_intent in aggregate_intents:
                return True

    return False


def _get_analysis_metadata(
    query_plan: Any,
) -> Dict[str, Any]:
    """
    Extract optional analysis metadata.
    """

    if not isinstance(query_plan, dict):
        return {}

    analyses = query_plan.get(
        "analyses",
        []
    )

    if (
        isinstance(analyses, list)
        and analyses
        and isinstance(
            analyses[0],
            dict,
        )
    ):
        return analyses[0]

    return {}


def _is_sensitive_result_column(
    column_name: str,
    query_plan: Any,
) -> bool:
    """
    Determine whether a result column is protected.

    We check against all tables available in the query plan.
    We also use the generic column-name detection with an empty
    table name as a fallback.
    """

    tables = _get_result_tables(
        query_plan
    )

    for table_name in tables:

        if is_table_blocked(
            table_name
        ):
            return True

        if _is_sensitive_column(
            column_name,
            table_name,
        ):
            return True

    # This also catches automatic sensitive-column patterns.
    if _is_sensitive_column(
        column_name,
        "",
    ):
        return True

    return False


# ============================================================
# SAFE VALUE CONVERSION
# ============================================================

def _safe_value(value: Any) -> Any:
    """
    Convert values into safe serializable representations.

    No objects with executable behavior are forwarded.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


# ============================================================
# RESULT FILTER
# ============================================================

def filter_result_for_ai(
    result: Any,
    query_plan: Any = None,
) -> Dict[str, Any]:
    """
    Create a Gemini-safe version of one database result.

    The original result is never modified.

    Returns:
        {
            "success": True,
            "columns": [...],
            "rows": [...],
            "row_count": ...,
            "ai_filtered": True,
            "ai_policy": {...}
        }
    """

    # --------------------------------------------------------
    # Invalid / missing result
    # --------------------------------------------------------

    if result is None:

        return {
            "success": False,
            "message": "No database result was returned.",
            "ai_filtered": True,
        }

    # --------------------------------------------------------
    # String results
    # --------------------------------------------------------

    if isinstance(
        result,
        str,
    ):

        return {
            "success": True,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "summary": result[:MAX_AI_RESULT_CHARACTERS],
            "ai_filtered": True,
        }

    # --------------------------------------------------------
    # List results
    # --------------------------------------------------------

    if isinstance(
        result,
        list,
    ):

        result = {
            "success": True,
            "columns": [],
            "rows": result,
            "row_count": len(result),
        }

    # --------------------------------------------------------
    # Unsupported result
    # --------------------------------------------------------

    if not isinstance(
        result,
        dict,
    ):

        return {
            "success": False,
            "message": (
                "Database result format is not supported "
                "for AI analysis."
            ),
            "ai_filtered": True,
        }

    # --------------------------------------------------------
    # Failed database query
    # --------------------------------------------------------

    if result.get(
        "success"
    ) is False:

        response = {
            "success": False,
            "message": (
                "The database query failed."
            ),
            "ai_filtered": True,
        }

        return response

    # --------------------------------------------------------
    # Read result metadata
    # --------------------------------------------------------

    columns = result.get(
        "columns",
        [],
    )

    rows = result.get(
        "rows",
        [],
    )

    row_count = result.get(
        "row_count",
        len(rows)
        if isinstance(rows, list)
        else 0,
    )

    if not isinstance(
        columns,
        list,
    ):
        columns = []

    if not isinstance(
        rows,
        list,
    ):
        rows = []

    # --------------------------------------------------------
    # Determine whether aggregate data is allowed
    # --------------------------------------------------------

    aggregate_result = (
        _has_aggregate_analysis(
            query_plan
        )
    )

    allow_values = (
        ALLOW_AGGREGATE_RESULTS
        and aggregate_result
    )

    # --------------------------------------------------------
    # Determine safe columns
    # --------------------------------------------------------

    safe_columns = []

    blocked_columns = []

    for column in columns:

        column_name = str(
            column
        )

        if _is_sensitive_result_column(
            column_name,
            query_plan,
        ):

            blocked_columns.append(
                column_name
            )

            continue

        if len(safe_columns) >= (
            MAX_AI_COLUMNS
        ):
            break

        safe_columns.append(
            column_name
        )

    # --------------------------------------------------------
    # If raw rows are not allowed and this is not an
    # aggregate result, send metadata only.
    # --------------------------------------------------------

    if not allow_values:

        return {
            "success": True,
            "columns": safe_columns,
            "row_count": row_count,
            "rows": [],
            "data_available_to_ai": False,
            "raw_rows_blocked": True,
            "aggregate_result": False,
            "blocked_columns": blocked_columns,
            "ai_filtered": True,
        }

    # --------------------------------------------------------
    # Raw rows explicitly allowed
    # --------------------------------------------------------

    if ALLOW_RAW_ROWS:

        selected_columns = safe_columns[
            :MAX_AI_COLUMNS
        ]

        selected_indexes = [
            columns.index(column)
            for column in selected_columns
        ]

        safe_rows = []

        for row in rows[
            :MAX_AI_ROWS
        ]:

            if isinstance(
                row,
                dict,
            ):

                safe_row = {}

                for column in selected_columns:

                    if column in row:
                        safe_row[column] = (
                            _safe_value(
                                row[column]
                            )
                        )

            elif isinstance(
                row,
                (list, tuple),
            ):

                safe_row = {}

                for index, column in zip(
                    selected_indexes,
                    selected_columns,
                ):

                    if index < len(row):
                        safe_row[column] = (
                            _safe_value(
                                row[index]
                            )
                        )

            else:

                safe_row = str(
                    row
                )

            safe_rows.append(
                safe_row
            )

        filtered = {
            "success": True,
            "columns": selected_columns,
            "row_count": row_count,
            "rows": safe_rows,
            "data_available_to_ai": True,
            "raw_rows_blocked": False,
            "aggregate_result": aggregate_result,
            "blocked_columns": blocked_columns,
            "ai_filtered": True,
        }

        return _limit_result_size(
            filtered
        )

    # --------------------------------------------------------
    # Aggregate results
    # --------------------------------------------------------
    #
    # For aggregate results we allow the returned values because
    # they are KPI/summary values rather than raw database rows.
    #
    # Sensitive columns have already been removed.
    # --------------------------------------------------------

    selected_columns = safe_columns

    selected_indexes = [
        columns.index(column)
        for column in selected_columns
    ]

    safe_rows = []

    for row in rows[
        :MAX_AI_ROWS
    ]:

        if isinstance(
            row,
            dict,
        ):

            safe_row = {}

            for column in selected_columns:

                if column in row:

                    safe_row[column] = (
                        _safe_value(
                            row[column]
                        )
                    )

        elif isinstance(
            row,
            (list, tuple),
        ):

            safe_row = {}

            for index, column in zip(
                selected_indexes,
                selected_columns,
            ):

                if index < len(row):

                    safe_row[column] = (
                        _safe_value(
                            row[index]
                        )
                    )

        else:

            safe_row = str(
                row
            )

        safe_rows.append(
            safe_row
        )

    filtered = {
        "success": True,
        "columns": selected_columns,
        "row_count": row_count,
        "rows": safe_rows,
        "data_available_to_ai": True,
        "raw_rows_blocked": False,
        "aggregate_result": True,
        "blocked_columns": blocked_columns,
        "ai_filtered": True,
    }

    return _limit_result_size(
        filtered
    )


# ============================================================
# RESULT SIZE LIMIT
# ============================================================

def _limit_result_size(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply the final character limit to the AI payload.

    This protects against unexpectedly large query results.
    """

    rows = result.get(
        "rows",
        [],
    )

    safe_rows = []

    current_size = 0

    for row in rows:

        row_text = str(
            row
        )

        if (
            current_size
            + len(row_text)
            > MAX_AI_RESULT_CHARACTERS
        ):
            break

        safe_rows.append(
            row
        )

        current_size += len(
            row_text
        )

    result["rows"] = safe_rows

    result["ai_result_characters"] = (
        current_size
    )

    result["ai_result_truncated"] = (
        len(safe_rows)
        < len(rows)
    )

    return result


# ============================================================
# MULTI-ANALYSIS FILTER
# ============================================================

def filter_results_for_ai(
    results: Any,
    query_plan: Any = None,
) -> List[Dict[str, Any]]:
    """
    Filter every database result before it reaches Gemini.

    This is the function that should be called by main.py.
    """

    if results is None:
        return []

    if not isinstance(
        results,
        list,
    ):
        results = [results]

    filtered_results = []

    analyses = []

    if isinstance(
        query_plan,
        dict,
    ):

        analyses = query_plan.get(
            "analyses",
            [],
        )

    for index, result in enumerate(
        results
    ):

        analysis_plan = query_plan

        if (
            index < len(analyses)
            and isinstance(
                analyses[index],
                dict,
            )
        ):

            analysis_plan = dict(
                query_plan
                if isinstance(
                    query_plan,
                    dict,
                )
                else {}
            )

            analysis_plan.update(
                analyses[index]
            )

        filtered_results.append(
            filter_result_for_ai(
                result=result,
                query_plan=analysis_plan,
            )
        )

    return filtered_results