import re

from typing import Any, Dict, List, Optional


# ============================================================
# SUPPORTED AGGREGATIONS
# ============================================================

SUPPORTED_AGGREGATIONS = {
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COUNT",
    "COUNT_DISTINCT",
    "NONE",
    "PERCENTAGE",
    "RATIO",
}


# ============================================================
# SUPPORTED OPERATORS
# ============================================================

SUPPORTED_OPERATORS = {
    "=",
    "!=",
    "<>",
    ">",
    ">=",
    "<",
    "<=",
    "LIKE",
    "NOT LIKE",
    "IN",
    "NOT IN",
    "IS NULL",
    "IS NOT NULL",
}


# ============================================================
# DIALECT
# ============================================================

def normalize_dialect(dialect: str) -> str:
    if not dialect:
        return "duckdb"

    value = str(dialect).strip().lower()

    if value in {
        "mysql",
        "mariadb",
    }:
        return "mysql"

    return "duckdb"


# ============================================================
# IDENTIFIERS
# ============================================================

def quote_identifier(
    identifier: str,
    dialect: str = "duckdb",
) -> str:

    dialect = normalize_dialect(dialect)

    identifier = str(identifier).strip()

    if not identifier:
        raise ValueError(
            "SQL identifier cannot be empty."
        )

    if dialect == "mysql":
        return (
            "`"
            + identifier.replace("`", "``")
            + "`"
        )

    return (
        '"'
        + identifier.replace('"', '""')
        + '"'
    )


# ============================================================
# COLUMN REFERENCES
# ============================================================

def quote_column_reference(
    column: str,
    dialect: str = "duckdb",
) -> str:

    if column is None:
        raise ValueError(
            "Column reference cannot be None."
        )

    column = str(column).strip()

    if not column:
        raise ValueError(
            "Column reference cannot be empty."
        )

    # SQL wildcard.
    if column == "*":
        return "*"

    # Already an expression.
    if column.upper() in {
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
    }:
        return column

    parts = [
        part.strip()
        for part in column.split(".")
        if part.strip()
    ]

    if not parts:
        raise ValueError(
            f"Invalid column reference: {column}"
        )

    return ".".join(
        quote_identifier(
            part,
            dialect,
        )
        for part in parts
    )


# ============================================================
# STRING VALUES
# ============================================================

def escape_sql_string(
    value: str,
    dialect: str = "duckdb",
) -> str:

    value = str(value)

    if normalize_dialect(dialect) == "mysql":
        value = value.replace(
            "\\",
            "\\\\",
        )

    return value.replace(
        "'",
        "''",
    )


# ============================================================
# SQL VALUE
# ============================================================

def sql_value(
    value: Any,
    dialect: str = "duckdb",
) -> str:

    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return (
            "TRUE"
            if value
            else "FALSE"
        )

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return str(value)

    text = str(value).strip()

    if text.lower() == "null":
        return "NULL"

    if text.lower() == "true":
        return "TRUE"

    if text.lower() == "false":
        return "FALSE"

    if re.fullmatch(
        r"-?\d+(\.\d+)?",
        text,
    ):
        return text

    if (
        len(text) >= 2
        and text[0] == "'"
        and text[-1] == "'"
    ):
        return text

    if (
        len(text) >= 2
        and text[0] == '"'
        and text[-1] == '"'
    ):
        text = text[1:-1]

    return (
        "'"
        + escape_sql_string(
            text,
            dialect,
        )
        + "'"
    )


# ============================================================
# IN VALUES
# ============================================================

def parse_in_values(
    value: Any,
) -> List[Any]:

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    text = str(value).strip()

    if (
        text.startswith("[")
        and text.endswith("]")
    ):
        text = text[1:-1].strip()

    if not text:
        return []

    values = []
    current = []
    quote = None

    for char in text:

        if char in {"'", '"'}:

            if quote is None:
                quote = char

            elif quote == char:
                quote = None

            current.append(char)

            continue

        if (
            char == ","
            and quote is None
        ):
            values.append(
                "".join(current).strip()
            )
            current = []
        else:
            current.append(char)

    if current:
        values.append(
            "".join(current).strip()
        )

    return [
        item
        for item in values
        if item != ""
    ]


# ============================================================
# FILTER
# ============================================================

def generate_filter_sql(
    condition: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    if not isinstance(condition, dict):
        raise ValueError(
            "Filter condition must be an object."
        )

    column = condition.get("column")
    operator = condition.get("operator")
    value = condition.get("value")

    if not column:
        raise ValueError(
            "Filter column is missing."
        )

    if not operator:
        raise ValueError(
            "Filter operator is missing."
        )

    operator = str(
        operator
    ).strip().upper()

    if operator not in SUPPORTED_OPERATORS:
        raise ValueError(
            f"Unsupported filter operator: {operator}"
        )

    column_sql = quote_column_reference(
        column,
        dialect,
    )

    # --------------------------------------------------------
    # NULL operators
    # --------------------------------------------------------

    if operator == "IS NULL":
        return f"{column_sql} IS NULL"

    if operator == "IS NOT NULL":
        return f"{column_sql} IS NOT NULL"

    # --------------------------------------------------------
    # IN
    # --------------------------------------------------------

    if operator in {
        "IN",
        "NOT IN",
    }:

        values = parse_in_values(value)

        if not values:
            raise ValueError(
                f"{operator} filter for '{column}' "
                "contains no values."
            )

        values_sql = ", ".join(
            sql_value(
                item,
                dialect,
            )
            for item in values
        )

        return (
            f"{column_sql} {operator} "
            f"({values_sql})"
        )

    # --------------------------------------------------------
    # LIKE
    # --------------------------------------------------------

    if operator in {
        "LIKE",
        "NOT LIKE",
    }:

        return (
            f"{column_sql} {operator} "
            f"{sql_value(value, dialect)}"
        )

    # --------------------------------------------------------
    # NULL equality
    # --------------------------------------------------------

    if (
        value is None
        or str(value).strip().lower() == "null"
    ):

        if operator == "=":
            return f"{column_sql} IS NULL"

        if operator in {
            "!=",
            "<>",
        }:
            return f"{column_sql} IS NOT NULL"

    # --------------------------------------------------------
    # Normal comparison
    # --------------------------------------------------------

    return (
        f"{column_sql} "
        f"{operator} "
        f"{sql_value(value, dialect)}"
    )


# ============================================================
# JOINS
# ============================================================

def validate_join(
    join: Dict[str, Any],
) -> None:

    if not isinstance(join, dict):
        raise ValueError(
            "Join must be an object."
        )

    for field in [
        "left_table",
        "left_column",
        "right_table",
        "right_column",
    ]:

        value = join.get(field)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"Join is missing '{field}'."
            )


def generate_join_sql(
    join: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    validate_join(join)

    left_table = join[
        "left_table"
    ].strip()

    left_column = join[
        "left_column"
    ].strip()

    right_table = join[
        "right_table"
    ].strip()

    right_column = join[
        "right_column"
    ].strip()

    return (
        "JOIN "
        + quote_identifier(
            right_table,
            dialect,
        )
        + " ON "
        + quote_column_reference(
            f"{left_table}.{left_column}",
            dialect,
        )
        + " = "
        + quote_column_reference(
            f"{right_table}.{right_column}",
            dialect,
        )
    )


def order_joins(
    joins: List[Dict[str, Any]],
    base_table: str,
) -> List[Dict[str, Any]]:

    if not joins:
        return []

    connected = {
        base_table
    }

    remaining = []
    seen_edges = set()

    for raw_join in joins:

        validate_join(raw_join)

        join = {
            "left_table": str(
                raw_join["left_table"]
            ).strip(),

            "left_column": str(
                raw_join["left_column"]
            ).strip(),

            "right_table": str(
                raw_join["right_table"]
            ).strip(),

            "right_column": str(
                raw_join["right_column"]
            ).strip(),
        }

        edge = (
            join["left_table"],
            join["left_column"],
            join["right_table"],
            join["right_column"],
        )

        reverse = (
            join["right_table"],
            join["right_column"],
            join["left_table"],
            join["left_column"],
        )

        if (
            edge in seen_edges
            or reverse in seen_edges
        ):
            continue

        seen_edges.add(edge)
        remaining.append(join)

    ordered = []

    while remaining:

        found = None
        oriented = None

        for index, join in enumerate(
            remaining
        ):

            left = join[
                "left_table"
            ]

            right = join[
                "right_table"
            ]

            if left in connected:

                found = index
                oriented = dict(join)
                break

            if right in connected:

                found = index

                oriented = {
                    "left_table":
                        join["right_table"],

                    "left_column":
                        join["right_column"],

                    "right_table":
                        join["left_table"],

                    "right_column":
                        join["left_column"],
                }

                break

        if found is None:
            raise ValueError(
                "JOIN relationships are disconnected "
                f"from base table '{base_table}'."
            )

        remaining.pop(found)

        ordered.append(oriented)

        connected.add(
            oriented["right_table"]
        )

    return ordered


# ============================================================
# METRIC RESOLUTION
# ============================================================

def resolve_metric_column(
    analysis: Dict[str, Any],
) -> str:
    """
    Resolve the metric dynamically.

    Supports both:
        metric_column
    and:
        metric

    This is important because the Gemini planner uses
    'metric', while older planner contracts may use
    'metric_column'.

    No dataset-specific names are hardcoded.
    """

    metric_column = analysis.get(
        "metric_column"
    )

    if (
        metric_column is not None
        and str(metric_column).strip()
    ):
        return str(
            metric_column
        ).strip()

    metric = analysis.get(
        "metric"
    )

    if (
        metric is not None
        and str(metric).strip()
    ):
        return str(
            metric
        ).strip()

    return ""


# ============================================================
# AGGREGATION
# ============================================================

def generate_aggregation_expression(
    aggregation: str,
    metric_column: Optional[str],
    dialect: str = "duckdb",
) -> str:

    aggregation = str(
        aggregation or "NONE"
    ).strip().upper()

    if aggregation not in SUPPORTED_AGGREGATIONS:
        raise ValueError(
            f"Unsupported aggregation: {aggregation}"
        )

    metric_column = (
        ""
        if metric_column is None
        else str(
            metric_column
        ).strip()
    )

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if aggregation == "COUNT":

        if (
            not metric_column
            or metric_column == "*"
        ):
            return "COUNT(*) AS result"

        return (
            "COUNT("
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # COUNT DISTINCT
    # --------------------------------------------------------

    if aggregation == "COUNT_DISTINCT":

        if (
            not metric_column
            or metric_column == "*"
        ):
            raise ValueError(
                "COUNT_DISTINCT requires a metric column."
            )

        return (
            "COUNT(DISTINCT "
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # SUM
    # --------------------------------------------------------

    if aggregation == "SUM":

        if (
            not metric_column
            or metric_column == "*"
        ):
            raise ValueError(
                "SUM requires a valid metric column. "
                "The planner did not provide one."
            )

        return (
            "SUM("
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # AVG
    # --------------------------------------------------------

    if aggregation == "AVG":

        if (
            not metric_column
            or metric_column == "*"
        ):
            raise ValueError(
                "AVG requires a valid metric column. "
                "The planner did not provide one."
            )

        return (
            "AVG("
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # MIN
    # --------------------------------------------------------

    if aggregation == "MIN":

        if (
            not metric_column
            or metric_column == "*"
        ):
            raise ValueError(
                "MIN requires a valid metric column. "
                "The planner did not provide one."
            )

        return (
            "MIN("
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # MAX
    # --------------------------------------------------------

    if aggregation == "MAX":

        if (
            not metric_column
            or metric_column == "*"
        ):
            raise ValueError(
                "MAX requires a valid metric column. "
                "The planner did not provide one."
            )

        return (
            "MAX("
            + quote_column_reference(
                metric_column,
                dialect,
            )
            + ") AS result"
        )

    # --------------------------------------------------------
    # NONE
    # --------------------------------------------------------

    if aggregation == "NONE":

        if not metric_column:
            return ""

        return (
            quote_column_reference(
                metric_column,
                dialect,
            )
            + " AS result"
        )

    raise ValueError(
        f"Unsupported aggregation: {aggregation}"
    )


# ============================================================
# GROUP BY
# ============================================================

def generate_group_by_sql(
    group_by: List[str],
    dialect: str = "duckdb",
) -> str:

    if not group_by:
        return ""

    columns = [
        quote_column_reference(
            column,
            dialect,
        )
        for column in group_by
        if column
    ]

    if not columns:
        return ""

    return (
        "GROUP BY "
        + ", ".join(columns)
    )


# ============================================================
# ORDER BY
# ============================================================

def generate_order_by_sql(
    sort_column: str,
    sort_direction: str,
    dialect: str = "duckdb",
) -> str:

    if not sort_column:
        return ""

    direction = str(
        sort_direction or "ASC"
    ).upper().strip()

    if direction not in {
        "ASC",
        "DESC",
    }:
        direction = "ASC"

    if (
        str(sort_column)
        .strip()
        .lower()
        == "result"
    ):
        return (
            "ORDER BY result "
            + direction
        )

    return (
        "ORDER BY "
        + quote_column_reference(
            sort_column,
            dialect,
        )
        + " "
        + direction
    )


# ============================================================
# LIMIT
# ============================================================

def generate_limit_sql(
    limit: Any,
) -> str:

    if limit is None:
        return ""

    try:
        limit = int(limit)
    except (
        TypeError,
        ValueError,
    ):
        return ""

    if limit <= 0:
        return ""

    return f"LIMIT {limit}"


# ============================================================
# CALCULATIONS
# ============================================================

def generate_percentage_sql(
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    calculation = analysis.get(
        "calculation",
        {},
    )

    numerator_column = calculation.get(
        "numerator_column"
    )

    denominator = calculation.get(
        "denominator"
    )

    operator = calculation.get(
        "numerator_operator"
    )

    value = calculation.get(
        "numerator_value"
    )

    if not numerator_column:
        raise ValueError(
            "Percentage calculation is missing "
            "numerator_column."
        )

    numerator_reference = quote_column_reference(
        numerator_column,
        dialect,
    )

    if (
        operator
        and value not in {
            None,
            "",
        }
    ):

        condition = (
            f"{numerator_reference} "
            f"{operator} "
            f"{sql_value(value, dialect)}"
        )

        numerator = (
            "SUM(CASE WHEN "
            f"{condition} "
            "THEN 1 ELSE 0 END)"
        )

    else:

        numerator = (
            f"COUNT({numerator_reference})"
        )

    if denominator:

        denominator_reference = (
            quote_column_reference(
                denominator,
                dialect,
            )
        )

        denominator_sql = (
            f"COUNT({denominator_reference})"
        )

    else:

        denominator_sql = "COUNT(*)"

    return (
        "100.0 * "
        f"{numerator} / NULLIF("
        f"{denominator_sql}, 0) AS result"
    )


def generate_ratio_sql(
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    calculation = analysis.get(
        "calculation",
        {},
    )

    numerator = calculation.get(
        "numerator_column"
    )

    denominator = calculation.get(
        "denominator"
    )

    if not numerator:
        raise ValueError(
            "Ratio calculation is missing "
            "numerator_column."
        )

    if not denominator:
        raise ValueError(
            "Ratio calculation is missing "
            "denominator."
        )

    return (
        "SUM("
        + quote_column_reference(
            numerator,
            dialect,
        )
        + ") / NULLIF(SUM("
        + quote_column_reference(
            denominator,
            dialect,
        )
        + "), 0) AS result"
    )


def generate_select_expressions(
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> List[str]:

    calculation = analysis.get(
        "calculation",
        {},
    )

    calculation_type = str(
        calculation.get(
            "type",
            "none",
        )
    ).lower()

    if calculation_type == "percentage":
        return [
            generate_percentage_sql(
                analysis,
                dialect,
            )
        ]

    if calculation_type == "ratio":
        return [
            generate_ratio_sql(
                analysis,
                dialect,
            )
        ]

    aggregation = str(
        analysis.get(
            "aggregation",
            "NONE",
        )
    ).upper()

    metric_column = resolve_metric_column(
        analysis
    )

    expression = generate_aggregation_expression(
        aggregation,
        metric_column,
        dialect,
    )

    if not expression:
        return []

    return [expression]


# ============================================================
# COLUMN LIST HELPERS
# ============================================================

def normalize_column_list(
    value: Any,
) -> List[str]:

    if value is None:
        return []

    if isinstance(
        value,
        str,
    ):
        value = [value]

    if not isinstance(
        value,
        list,
    ):
        return []

    result = []

    for item in value:

        if isinstance(item, dict):

            text = str(
                item.get(
                    "column",
                    item.get(
                        "name",
                        "",
                    ),
                )
                or ""
            ).strip()

        else:

            text = str(
                item or ""
            ).strip()

        if (
            text
            and text not in result
        ):
            result.append(text)

    return result


def is_entity_listing(
    analysis: Dict[str, Any],
) -> bool:

    intent = str(
        analysis.get(
            "intent",
            "",
        )
    ).strip().lower()

    aggregation = str(
        analysis.get(
            "aggregation",
            "NONE",
        )
    ).strip().upper()

    output_columns = normalize_column_list(
        analysis.get(
            "output_columns"
        )
    )

    group_by = normalize_column_list(
        analysis.get(
            "group_by"
        )
    )

    ranking = analysis.get(
        "ranking"
    )

    # Explicit planner intent.
    if intent in {
        "entity_listing",
        "list",
        "listing",
        "record_listing",
        "records",
    }:
        return True

    # Generic structural signal.
    if (
        output_columns
        and aggregation == "NONE"
        and not group_by
        and not ranking
    ):
        return True

    return False


def build_listing_select(
    analysis: Dict[str, Any],
    dialect: str,
) -> List[str]:

    output_columns = normalize_column_list(
        analysis.get(
            "output_columns"
        )
    )

    if not output_columns:
        raise ValueError(
            "Entity-listing analysis requires "
            "output_columns."
        )

    return [
        quote_column_reference(
            column,
            dialect,
        )
        for column in output_columns
    ]


# ============================================================
# SORT RESOLUTION
# ============================================================

def resolve_sort_column(
    analysis: Dict[str, Any],
) -> str:

    sort_column = str(
        analysis.get(
            "sort_column",
            "",
        ) or ""
    ).strip()

    if not sort_column:
        return ""

    if sort_column.lower() == "result":
        return "result"

    aggregation = str(
        analysis.get(
            "aggregation",
            "NONE",
        )
    ).upper()

    metric_column = resolve_metric_column(
        analysis
    )

    group_by = normalize_column_list(
        analysis.get(
            "group_by"
        )
    )

    if (
        aggregation in {
            "COUNT",
            "COUNT_DISTINCT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
        }
        and metric_column
        and sort_column.lower()
        == metric_column.lower()
    ):
        return "result"

    if (
        aggregation in {
            "COUNT",
            "COUNT_DISTINCT",
        }
        and group_by
        and sort_column not in group_by
    ):
        return "result"

    return sort_column


# ============================================================
# RANKING
# ============================================================

def get_ranking_definition(
    analysis: Dict[str, Any],
) -> Optional[Dict[str, Any]]:

    ranking = analysis.get(
        "ranking"
    )

    if not isinstance(
        ranking,
        dict,
    ):
        return None

    partition_by = normalize_column_list(
        ranking.get(
            "partition_by"
        )
    )

    primary = ranking.get(
        "primary",
        {},
    )

    if not isinstance(
        primary,
        dict,
    ):
        primary = {}

    primary_column = str(
        primary.get(
            "column",
            "",
        ) or ""
    ).strip()

    if not primary_column:
        return None

    primary_aggregation = str(
        primary.get(
            "aggregation",
            "NONE",
        ) or "NONE"
    ).upper().strip()

    direction = str(
        primary.get(
            "direction",
            "DESC",
        ) or "DESC"
    ).upper().strip()

    if direction not in {
        "ASC",
        "DESC",
    }:
        direction = "DESC"

    tie_breakers = []

    for item in ranking.get(
        "tie_breakers",
        [],
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        column = str(
            item.get(
                "column",
                "",
            ) or ""
        ).strip()

        if not column:
            continue

        aggregation = str(
            item.get(
                "aggregation",
                "NONE",
            ) or "NONE"
        ).upper().strip()

        tie_direction = str(
            item.get(
                "direction",
                "DESC",
            ) or "DESC"
        ).upper().strip()

        if tie_direction not in {
            "ASC",
            "DESC",
        }:
            tie_direction = "DESC"

        tie_breakers.append(
            {
                "column": column,
                "aggregation": aggregation,
                "direction": tie_direction,
            }
        )

    try:
        limit = int(
            ranking.get(
                "limit",
                1,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        limit = 1

    if limit <= 0:
        limit = 1

    return {
        "partition_by": partition_by,

        "primary": {
            "column": primary_column,
            "aggregation": primary_aggregation,
            "direction": direction,
        },

        "tie_breakers": tie_breakers,

        "limit": limit,
    }


def ranking_aggregation_expression(
    aggregation: str,
    column: str,
    dialect: str,
) -> str:

    aggregation = str(
        aggregation or "NONE"
    ).upper().strip()

    if aggregation == "COUNT" and (
        not column
        or column == "*"
    ):
        return "COUNT(*)"

    if (
        aggregation == "COUNT"
    ):
        return (
            "COUNT("
            + quote_column_reference(
                column,
                dialect,
            )
            + ")"
        )

    if aggregation == "COUNT_DISTINCT":

        if not column or column == "*":
            raise ValueError(
                "COUNT_DISTINCT ranking "
                "requires a column."
            )

        return (
            "COUNT(DISTINCT "
            + quote_column_reference(
                column,
                dialect,
            )
            + ")"
        )

    reference = quote_column_reference(
        column,
        dialect,
    )

    if aggregation == "SUM":
        return f"SUM({reference})"

    if aggregation == "AVG":
        return f"AVG({reference})"

    if aggregation == "MIN":
        return f"MIN({reference})"

    if aggregation == "MAX":
        return f"MAX({reference})"

    if aggregation == "NONE":
        return reference

    raise ValueError(
        f"Unsupported ranking aggregation: "
        f"{aggregation}"
    )


# ============================================================
# GROUPED RANKING
# ============================================================

def generate_grouped_ranking_sql(
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    ranking = get_ranking_definition(
        analysis
    )

    if not ranking:
        raise ValueError(
            "Grouped ranking information is missing."
        )

    base_table = str(
        analysis.get(
            "table",
            "",
        ) or ""
    ).strip()

    if not base_table:

        tables = analysis.get(
            "tables",
            [],
        )

        if tables:
            base_table = str(
                tables[0]
            ).strip()

    if not base_table:
        raise ValueError(
            "No base table was provided."
        )

    joins = analysis.get(
        "joins",
        [],
    )

    if not isinstance(
        joins,
        list,
    ):
        joins = []

    joins = order_joins(
        joins,
        base_table,
    )

    filters = analysis.get(
        "filters",
        [],
    )

    if not isinstance(
        filters,
        list,
    ):
        filters = []

    output_columns = normalize_column_list(
        analysis.get(
            "output_columns"
        )
    )

    if not output_columns:
        output_columns = normalize_column_list(
            analysis.get(
                "group_by"
            )
        )

    partition_by = ranking[
        "partition_by"
    ]

    for column in partition_by:

        if column not in output_columns:
            output_columns.insert(
                0,
                column,
            )

    if not output_columns:
        raise ValueError(
            "Grouped ranking requires output_columns."
        )

    inner_select = []

    for index, column in enumerate(
        output_columns
    ):

        inner_select.append(
            quote_column_reference(
                column,
                dialect,
            )
            + " AS "
            + quote_identifier(
                f"__q_output_{index}",
                dialect,
            )
        )

    primary = ranking[
        "primary"
    ]

    inner_select.append(
        ranking_aggregation_expression(
            primary["aggregation"],
            primary["column"],
            dialect,
        )
        + " AS "
        + quote_identifier(
            "__q_primary_rank",
            dialect,
        )
    )

    for index, tie in enumerate(
        ranking["tie_breakers"]
    ):

        inner_select.append(
            ranking_aggregation_expression(
                tie["aggregation"],
                tie["column"],
                dialect,
            )
            + " AS "
            + quote_identifier(
                f"__q_tie_{index}",
                dialect,
            )
        )

    sql = [
        "WITH grouped_data AS (",
        "    SELECT",
        "        "
        + ",\n        ".join(
            inner_select
        ),
        "    FROM "
        + quote_identifier(
            base_table,
            dialect,
        ),
    ]

    for join in joins:

        sql.append(
            "    "
            + generate_join_sql(
                join,
                dialect,
            )
        )

    where_conditions = [
        generate_filter_sql(
            condition,
            dialect,
        )
        for condition in filters
    ]

    if where_conditions:

        sql.append(
            "    WHERE "
            + "\n      AND ".join(
                where_conditions
            )
        )

    grouping = []

    for column in output_columns:

        if column not in grouping:
            grouping.append(column)

    group_by_sql = generate_group_by_sql(
        grouping,
        dialect,
    )

    if group_by_sql:

        sql.append(
            "    "
            + group_by_sql
        )

    sql.extend(
        [
            "), ranked_data AS (",
        ]
    )

    outer_columns = []

    for index in range(
        len(output_columns)
    ):

        alias = (
            f"__q_output_{index}"
        )

        outer_columns.append(
            quote_identifier(
                alias,
                dialect,
            )
        )

    outer_columns.append(
        quote_identifier(
            "__q_primary_rank",
            dialect,
        )
    )

    partition_sql = ", ".join(
        quote_identifier(
            f"__q_output_{index}",
            dialect,
        )
        for index, _ in enumerate(
            partition_by
        )
    )

    order_parts = [
        quote_identifier(
            "__q_primary_rank",
            dialect,
        )
        + " "
        + primary["direction"]
    ]

    for index, tie in enumerate(
        ranking["tie_breakers"]
    ):

        order_parts.append(
            quote_identifier(
                f"__q_tie_{index}",
                dialect,
            )
            + " "
            + tie["direction"]
        )

    sql.extend(
        [
            "    SELECT",
            "        "
            + ",\n        ".join(
                outer_columns
            )
            + ",",
            "        ROW_NUMBER() OVER (",
        ]
    )

    if partition_sql:

        sql.extend(
            [
                "            PARTITION BY "
                + partition_sql,
            ]
        )

    sql.extend(
        [
            "            ORDER BY "
            + ", ".join(
                order_parts
            ),
            "        ) AS "
            + quote_identifier(
                "__q_rank",
                dialect,
            ),
            "    FROM grouped_data",
            ")",
            "SELECT",
        ]
    )

    final_columns = []

    for index, column in enumerate(
        output_columns
    ):

        final_columns.append(
            quote_identifier(
                f"__q_output_{index}",
                dialect,
            )
            + " AS "
            + quote_column_reference(
                column,
                dialect,
            )
        )

    final_columns.append(
        quote_identifier(
            "__q_primary_rank",
            dialect,
        )
        + " AS result"
    )

    sql.append(
        "    "
        + ",\n    ".join(
            final_columns
        )
    )

    sql.append(
        "FROM ranked_data"
    )

    sql.append(
        "WHERE "
        + quote_identifier(
            "__q_rank",
            dialect,
        )
        + " <= "
        + str(
            ranking["limit"]
        )
    )

    return "\n".join(sql) + ";"


# ============================================================
# HAVING
# ============================================================

def generate_having_condition_sql(
    condition: Dict[str, Any],
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:
    """
    Generate a HAVING condition dynamically.

    Example planner condition:

        {
            "column": "payment.amount",
            "operator": ">",
            "value": 200
        }

    Combined with:

        aggregation = SUM
        metric = payment.amount

    becomes:

        SUM("payment"."amount") > 200

    No dataset-specific logic is used.
    """

    if not isinstance(
        condition,
        dict,
    ):
        raise ValueError(
            "HAVING condition must be an object."
        )

    column = str(
        condition.get(
            "column",
            "",
        ) or ""
    ).strip()

    operator = str(
        condition.get(
            "operator",
            "",
        ) or ""
    ).strip().upper()

    value = condition.get(
        "value"
    )

    if not column:
        raise ValueError(
            "HAVING condition is missing column."
        )

    if not operator:
        raise ValueError(
            "HAVING condition is missing operator."
        )

    if operator not in SUPPORTED_OPERATORS:
        raise ValueError(
            f"Unsupported HAVING operator: {operator}"
        )

    # --------------------------------------------------------
    # Resolve aggregate metric
    # --------------------------------------------------------

    aggregation = str(
        analysis.get(
            "aggregation",
            "NONE",
        ) or "NONE"
    ).upper().strip()

    metric_column = resolve_metric_column(
        analysis
    )

    # --------------------------------------------------------
    # If planner says "result", use the aggregate result.
    # --------------------------------------------------------

    if column.lower() == "result":

        if aggregation in {
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "COUNT",
            "COUNT_DISTINCT",
        }:

            if aggregation == "COUNT":

                if (
                    not metric_column
                    or metric_column == "*"
                ):
                    expression = "COUNT(*)"
                else:
                    expression = (
                        "COUNT("
                        + quote_column_reference(
                            metric_column,
                            dialect,
                        )
                        + ")"
                    )

            elif aggregation == "COUNT_DISTINCT":

                if not metric_column:
                    raise ValueError(
                        "COUNT_DISTINCT HAVING "
                        "requires a metric."
                    )

                expression = (
                    "COUNT(DISTINCT "
                    + quote_column_reference(
                        metric_column,
                        dialect,
                    )
                    + ")"
                )

            else:

                if not metric_column:
                    raise ValueError(
                        f"{aggregation} HAVING "
                        "requires a metric column."
                    )

                expression = (
                    aggregation
                    + "("
                    + quote_column_reference(
                        metric_column,
                        dialect,
                    )
                    + ")"
                )

        else:
            expression = "result"

    # --------------------------------------------------------
    # If HAVING column equals the metric, aggregate it.
    # --------------------------------------------------------

    elif (
        metric_column
        and column.lower()
        == metric_column.lower()
        and aggregation in {
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "COUNT",
            "COUNT_DISTINCT",
        }
    ):

        if aggregation == "COUNT":

            expression = (
                "COUNT("
                + quote_column_reference(
                    metric_column,
                    dialect,
                )
                + ")"
            )

        elif aggregation == "COUNT_DISTINCT":

            expression = (
                "COUNT(DISTINCT "
                + quote_column_reference(
                    metric_column,
                    dialect,
                )
                + ")"
            )

        else:

            expression = (
                aggregation
                + "("
                + quote_column_reference(
                    metric_column,
                    dialect,
                )
                + ")"
            )

    # --------------------------------------------------------
    # Generic fallback:
    #
    # If the planner gives another grouped column, don't
    # invent an aggregation.
    # --------------------------------------------------------

    else:

        expression = quote_column_reference(
            column,
            dialect,
        )

    # --------------------------------------------------------
    # NULL operators
    # --------------------------------------------------------

    if operator == "IS NULL":
        return f"{expression} IS NULL"

    if operator == "IS NOT NULL":
        return f"{expression} IS NOT NULL"

    # --------------------------------------------------------
    # IN / NOT IN
    # --------------------------------------------------------

    if operator in {
        "IN",
        "NOT IN",
    }:

        values = parse_in_values(value)

        if not values:
            raise ValueError(
                "HAVING IN condition contains no values."
            )

        values_sql = ", ".join(
            sql_value(
                item,
                dialect,
            )
            for item in values
        )

        return (
            f"{expression} {operator} "
            f"({values_sql})"
        )

    # --------------------------------------------------------
    # LIKE
    # --------------------------------------------------------

    if operator in {
        "LIKE",
        "NOT LIKE",
    }:

        return (
            f"{expression} {operator} "
            f"{sql_value(value, dialect)}"
        )

    # --------------------------------------------------------
    # NULL comparison
    # --------------------------------------------------------

    if (
        value is None
        or str(value).strip().lower()
        == "null"
    ):

        if operator == "=":
            return f"{expression} IS NULL"

        if operator in {
            "!=",
            "<>",
        }:
            return f"{expression} IS NOT NULL"

    return (
        f"{expression} "
        f"{operator} "
        f"{sql_value(value, dialect)}"
    )


def generate_having_sql(
    having: Any,
    analysis: Dict[str, Any],
    dialect: str = "duckdb",
) -> str:

    if not having:
        return ""

    if not isinstance(
        having,
        list,
    ):
        having = [having]

    conditions = []

    for condition in having:

        if not isinstance(
            condition,
            dict,
        ):
            continue

        conditions.append(
            generate_having_condition_sql(
                condition,
                analysis,
                dialect,
            )
        )

    if not conditions:
        return ""

    return (
        "HAVING "
        + "\n  AND ".join(
            conditions
        )
    )


# ============================================================
# MAIN SQL GENERATOR
# ============================================================

def generate_sql(
    analysis: Dict[str, Any],
    schema_context: str = "",
    dialect: str = "duckdb",
) -> str:

    if not isinstance(
        analysis,
        dict,
    ):
        raise ValueError(
            "Analysis must be an object."
        )

    dialect = normalize_dialect(
        dialect
    )

    # --------------------------------------------------------
    # GROUPED RANKING
    # --------------------------------------------------------

    ranking = get_ranking_definition(
        analysis
    )

    if (
        ranking
        and ranking["partition_by"]
    ):

        return generate_grouped_ranking_sql(
            analysis,
            dialect,
        )

    # --------------------------------------------------------
    # BASE TABLE
    # --------------------------------------------------------

    base_table = str(
        analysis.get(
            "table",
            "",
        ) or ""
    ).strip()

    if not base_table:

        tables = analysis.get(
            "tables",
            [],
        )

        if tables:
            base_table = str(
                tables[0]
            ).strip()

    if not base_table:
        raise ValueError(
            "No base table was provided."
        )

    # --------------------------------------------------------
    # JOINS
    # --------------------------------------------------------

    joins = analysis.get(
        "joins",
        [],
    )

    if not isinstance(
        joins,
        list,
    ):
        joins = []

    joins = order_joins(
        joins,
        base_table,
    )

    # --------------------------------------------------------
    # OUTPUT COLUMNS
    # --------------------------------------------------------

    output_columns = normalize_column_list(
        analysis.get(
            "output_columns"
        )
    )

    # --------------------------------------------------------
    # GROUP BY
    # --------------------------------------------------------

    group_by = normalize_column_list(
        analysis.get(
            "group_by"
        )
    )

    # ========================================================
    # ENTITY LISTING
    # ========================================================

    if is_entity_listing(
        analysis
    ):

        select_parts = (
            build_listing_select(
                analysis,
                dialect,
            )
        )

    else:

        select_parts = []

        # ----------------------------------------------------
        # GROUP COLUMNS
        # ----------------------------------------------------

        for column in group_by:

            quoted = quote_column_reference(
                column,
                dialect,
            )

            if quoted not in select_parts:

                select_parts.append(
                    quoted
                )

        # ----------------------------------------------------
        # Planner-selected output columns
        # ----------------------------------------------------

        for column in output_columns:

            quoted = quote_column_reference(
                column,
                dialect,
            )

            if quoted not in select_parts:

                select_parts.append(
                    quoted
                )

        # ----------------------------------------------------
        # CALCULATED METRIC
        # ----------------------------------------------------

        aggregation = str(
            analysis.get(
                "aggregation",
                "NONE",
            )
        ).upper().strip()

        metric_column = resolve_metric_column(
            analysis
        )

        calculation = analysis.get(
            "calculation",
            {},
        )

        if not isinstance(
            calculation,
            dict,
        ):
            calculation = {}

        calculation_type = str(
            calculation.get(
                "type",
                "none",
            )
        ).lower()

        # Do not generate an empty result expression for
        # NONE without a metric.
        if (
            metric_column
            or calculation_type in {
                "percentage",
                "ratio",
            }
            or aggregation != "NONE"
        ):

            metric_expressions = (
                generate_select_expressions(
                    analysis,
                    dialect,
                )
            )

            for expression in metric_expressions:

                if (
                    expression
                    and expression not in select_parts
                ):

                    select_parts.append(
                        expression
                    )

    if not select_parts:
        raise ValueError(
            "No SELECT expressions could be generated."
        )

    # --------------------------------------------------------
    # SQL START
    # --------------------------------------------------------

    sql_parts = [
        "SELECT",
        "    "
        + ",\n    ".join(
            select_parts
        ),
        "FROM "
        + quote_identifier(
            base_table,
            dialect,
        ),
    ]

    # --------------------------------------------------------
    # JOINS
    # --------------------------------------------------------

    for join in joins:

        sql_parts.append(
            generate_join_sql(
                join,
                dialect,
            )
        )

    # --------------------------------------------------------
    # FILTERS / WHERE
    # --------------------------------------------------------

    filters = analysis.get(
        "filters",
        [],
    )

    if not isinstance(
        filters,
        list,
    ):
        filters = []

    where_conditions = [
        generate_filter_sql(
            condition,
            dialect,
        )
        for condition in filters
        if isinstance(
            condition,
            dict,
        )
    ]

    if where_conditions:

        sql_parts.append(
            "WHERE "
            + "\n  AND ".join(
                where_conditions
            )
        )

    # --------------------------------------------------------
    # GROUP BY
    # --------------------------------------------------------

    group_by_sql = generate_group_by_sql(
        group_by,
        dialect,
    )

    if group_by_sql:

        sql_parts.append(
            group_by_sql
        )

    # --------------------------------------------------------
    # HAVING
    # --------------------------------------------------------

    having_sql = generate_having_sql(
        analysis.get(
            "having",
            [],
        ),
        analysis,
        dialect,
    )

    if having_sql:

        sql_parts.append(
            having_sql
        )

    # --------------------------------------------------------
    # ORDER BY
    # --------------------------------------------------------

    sort_column = resolve_sort_column(
        analysis
    )

    sort_direction = analysis.get(
        "sort_direction",
        "ASC",
    )

    # --------------------------------------------------------
    # Ranking compatibility
    # --------------------------------------------------------

    if (
        ranking
        and not ranking["partition_by"]
    ):

        primary = ranking["primary"]

        if not sort_column:

            sort_column = "result"

        sort_direction = primary[
            "direction"
        ]

    order_by_sql = generate_order_by_sql(
        sort_column,
        sort_direction,
        dialect,
    )

    if order_by_sql:

        sql_parts.append(
            order_by_sql
        )

    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    limit = analysis.get(
        "limit"
    )

    if (
        ranking
        and not ranking["partition_by"]
        and not limit
    ):

        limit = ranking["limit"]

    limit_sql = generate_limit_sql(
        limit
    )

    if limit_sql:

        sql_parts.append(
            limit_sql
        )

    # --------------------------------------------------------
    # FINAL SQL
    # --------------------------------------------------------

    sql = "\n".join(
        sql_parts
    ).strip()

    if not sql.endswith(";"):
        sql += ";"

    return sql


# ============================================================
# MULTIPLE ANALYSES
# ============================================================

def generate_sql_strings(
    plan: Dict[str, Any],
    schema_context: str = "",
    dialect: str = "duckdb",
) -> List[str]:

    if not isinstance(
        plan,
        dict,
    ):
        raise ValueError(
            "Plan must be an object."
        )

    analyses = plan.get(
        "analyses",
        [],
    )

    if not isinstance(
        analyses,
        list,
    ):
        raise ValueError(
            "Plan analyses must be a list."
        )

    queries = []

    for analysis in analyses:

        queries.append(
            generate_sql(
                analysis,
                schema_context=schema_context,
                dialect=dialect,
            )
        )

    return queries


# ============================================================
# BACKWARDS COMPATIBILITY
# ============================================================

def generate_queries(
    plan: Dict[str, Any],
    schema_context: str = "",
    dialect: str = "duckdb",
) -> List[str]:

    return generate_sql_strings(
        plan,
        schema_context=schema_context,
        dialect=dialect,
    )


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # Generic entity listing test
    # --------------------------------------------------------

    listing_plan = {
        "intent": "entity_listing",

        "table": "example_table",

        "tables": [
            "example_table",
        ],

        "joins": [],

        "metric_column": "",

        "metric": "",

        "aggregation": "NONE",

        "calculation": {
            "type": "none",
            "numerator_column": "",
            "numerator_operator": "",
            "numerator_value": "",
            "denominator": "",
        },

        "group_by": [],

        "filters": [
            {
                "column": "example_table.available_value",
                "operator": ">",
                "value": 0,
            }
        ],

        "having": [],

        "sort_column": "example_table.available_value",

        "sort_direction": "DESC",

        "limit": 0,

        "date_column": "",

        "output_columns": [
            "example_table.identifier",
            "example_table.description",
            "example_table.available_value",
        ],

        "ranking": None,
    }

    print(
        "============================================================"
    )

    print(
        "ENTITY LISTING TEST"
    )

    print(
        "============================================================"
    )

    print(
        generate_sql(
            listing_plan,
            dialect="mysql",
        )
    )

    print()

    # --------------------------------------------------------
    # JOIN ranking test
    # --------------------------------------------------------

    join_plan = {
        "intent": "ranking",

        "table": "film_actor",

        "tables": [
            "film_actor",
            "actor",
        ],

        "joins": [
            {
                "left_table": "film_actor",
                "left_column": "actor_id",
                "right_table": "actor",
                "right_column": "actor_id",
            }
        ],

        "metric_column": "film_actor.film_id",

        "metric": "film_actor.film_id",

        "aggregation": "COUNT",

        "calculation": {
            "type": "none",
            "numerator_column": "",
            "numerator_operator": "",
            "numerator_value": "",
            "denominator": "",
        },

        "group_by": [
            "actor.first_name",
            "actor.last_name",
        ],

        "filters": [],

        "having": [],

        "sort_column": "film_actor.film_id",

        "sort_direction": "DESC",

        "limit": 1,

        "date_column": "",

        "output_columns": [
            "actor.first_name",
            "actor.last_name",
        ],

        "ranking": None,
    }

    print(
        "============================================================"
    )

    print(
        "JOIN TEST"
    )

    print(
        "============================================================"
    )

    print(
        generate_sql(
            join_plan,
            dialect="mysql",
        )
    )

    print()

    # --------------------------------------------------------
    # Dynamic aggregate + HAVING test
    # --------------------------------------------------------

    revenue_plan = {
        "intent": "ranking",

        "table": "film",

        "tables": [
            "film",
            "inventory",
            "rental",
            "payment",
        ],

        "joins": [
            {
                "left_table": "film",
                "left_column": "film_id",
                "right_table": "inventory",
                "right_column": "film_id",
            },
            {
                "left_table": "inventory",
                "left_column": "inventory_id",
                "right_table": "rental",
                "right_column": "inventory_id",
            },
            {
                "left_table": "rental",
                "left_column": "rental_id",
                "right_table": "payment",
                "right_column": "rental_id",
            },
        ],

        # IMPORTANT:
        # This represents what Gemini should dynamically
        # identify from the schema/question.
        "metric": "payment.amount",

        # metric_column is intentionally omitted here.
        # The generator must resolve metric dynamically.

        "aggregation": "SUM",

        "calculation": {
            "type": "none",
        },

        "group_by": [
            "film.title",
        ],

        "output_columns": [
            "film.title",
        ],

        "filters": [],

        "having": [
            {
                "column": "payment.amount",
                "operator": ">",
                "value": 200,
            }
        ],

        "sort_column": "payment.amount",

        "sort_direction": "DESC",

        "limit": 3,

        "ranking": None,
    }

    print(
        "============================================================"
    )

    print(
        "DYNAMIC AGGREGATION + HAVING TEST"
    )

    print(
        "============================================================"
    )

    print(
        generate_sql(
            revenue_plan,
            dialect="mysql",
        )
    )