import sqlite3


ALLOWED_OPERATORS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "LIKE"
}


ALLOWED_AGGREGATIONS = {
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COUNT",
    "NONE"
}


def quote_identifier(name):

    return '"' + str(name).replace(
        '"',
        '""'
    ) + '"'


def quote_value(value):

    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        return str(value)

    value = str(value)

    escaped = value.replace(
        "'",
        "''"
    )

    return f"'{escaped}'"


def get_table_columns(
    database_path,
    table
):

    conn = sqlite3.connect(
        database_path
    )

    try:

        rows = conn.execute(
            f'PRAGMA table_info({quote_identifier(table)})'
        ).fetchall()

        return {
            row[1]: row[2]
            for row in rows
        }

    finally:

        conn.close()


def value_exists(
    database_path,
    table,
    column,
    value
):

    conn = sqlite3.connect(
        database_path
    )

    try:

        sql = f'''
        SELECT 1
        FROM {quote_identifier(table)}
        WHERE LOWER(CAST(
            {quote_identifier(column)}
            AS TEXT
        )) = LOWER(?)
        LIMIT 1
        '''

        result = conn.execute(
            sql,
            (str(value),)
        ).fetchone()

        return result is not None

    finally:

        conn.close()


def validate_plan(
    plan,
    database_path
):

    if not isinstance(plan, dict):

        raise ValueError(
            "Query plan must be an object."
        )

    required = [
        "intent",
        "table",
        "filters",
        "metric",
        "group_by",
        "sort",
        "limit"
    ]

    for field in required:

        if field not in plan:

            raise ValueError(
                f"Query plan missing: {field}"
            )

    table = plan["table"]

    columns = get_table_columns(
        database_path,
        table
    )

    if not columns:

        raise ValueError(
            f"Table does not exist: {table}"
        )

    # --------------------------------------------------------
    # Validate filters
    # --------------------------------------------------------

    for filter_item in plan["filters"]:

        column = filter_item.get(
            "column"
        )

        operator = filter_item.get(
            "operator"
        )

        value = filter_item.get(
            "value"
        )

        if column not in columns:

            raise ValueError(
                f"Invalid filter column: {column}"
            )

        if operator not in ALLOWED_OPERATORS:

            raise ValueError(
                f"Invalid operator: {operator}"
            )

        # Don't check numeric values against
        # distinct text values.
        if operator == "=":

            column_type = str(
                columns[column]
            ).upper()

            if column_type in (
                "TEXT",
                "VARCHAR",
                "CHAR"
            ):

                if not value_exists(
                    database_path,
                    table,
                    column,
                    value
                ):

                    raise ValueError(
                        f"Value does not exist "
                        f"in database: "
                        f"{column} = {value}"
                    )

    # --------------------------------------------------------
    # Validate metric
    # --------------------------------------------------------

    metric = plan["metric"]

    metric_column = metric.get(
        "column"
    )

    aggregation = str(
        metric.get(
            "aggregation",
            "NONE"
        )
    ).upper()

    if aggregation not in ALLOWED_AGGREGATIONS:

        raise ValueError(
            f"Invalid aggregation: {aggregation}"
        )

    if metric_column not in (
        "",
        "*",
        None
    ):

        if metric_column not in columns:

            raise ValueError(
                f"Invalid metric column: "
                f"{metric_column}"
            )

    # --------------------------------------------------------
    # Validate group by
    # --------------------------------------------------------

    for column in plan["group_by"]:

        if column not in columns:

            raise ValueError(
                f"Invalid group-by column: "
                f"{column}"
            )

    # --------------------------------------------------------
    # Validate sort
    # --------------------------------------------------------

    sort = plan["sort"]

    sort_column = sort.get(
        "column",
        ""
    )

    sort_direction = str(
        sort.get(
            "direction",
            "ASC"
        )
    ).upper()

    if sort_direction not in (
        "ASC",
        "DESC"
    ):

        raise ValueError(
            "Invalid sort direction."
        )

    if sort_column:

        if (
            sort_column not in columns
            and sort_column != metric_column
        ):

            raise ValueError(
                f"Invalid sort column: "
                f"{sort_column}"
            )

    # --------------------------------------------------------
    # Validate limit
    # --------------------------------------------------------

    limit = plan.get(
        "limit"
    )

    if limit is not None:

        try:

            limit = int(limit)

        except Exception:

            raise ValueError(
                "Limit must be an integer."
            )

        if limit <= 0:

            raise ValueError(
                "Limit must be greater than zero."
            )

    return True


def build_sql(
    plan,
    database_path
):

    validate_plan(
        plan,
        database_path
    )

    table = plan["table"]

    intent = plan["intent"]

    filters = plan["filters"]

    metric = plan["metric"]

    metric_column = metric.get(
        "column"
    )

    aggregation = str(
        metric.get(
            "aggregation",
            "NONE"
        )
    ).upper()

    group_by = plan["group_by"]

    sort = plan["sort"]

    sort_column = sort.get(
        "column",
        ""
    )

    sort_direction = str(
        sort.get(
            "direction",
            "ASC"
        )
    ).upper()

    limit = plan.get(
        "limit"
    )

    # ========================================================
    # SELECT
    # ========================================================

    if intent == "count":

        select_clause = "COUNT(*) AS result"

    elif aggregation != "NONE":

        if metric_column in (
            None,
            "",
            "*"
        ):

            raise ValueError(
                "Aggregation requires a metric column."
            )

        select_clause = (
            f'{aggregation}('
            f'{quote_identifier(metric_column)}'
            f') AS result'
        )

    else:

        select_clause = "*"

    # ========================================================
    # GROUP BY
    # ========================================================

    if group_by:

        group_columns = ", ".join(
            quote_identifier(column)
            for column in group_by
        )

        if aggregation != "NONE":

            select_clause = (
                group_columns
                + ", "
                + select_clause
            )

    # ========================================================
    # FROM
    # ========================================================

    sql = (
        f'SELECT {select_clause}\n'
        f'FROM {quote_identifier(table)}'
    )

    # ========================================================
    # WHERE
    # ========================================================

    where_parts = []

    for filter_item in filters:

        column = filter_item["column"]
        operator = filter_item["operator"]
        value = filter_item["value"]

        quoted_column = quote_identifier(
            column
        )

        # Text equality
        if operator == "=":

            condition = (
                f'LOWER(CAST('
                f'{quoted_column} AS TEXT'
                f')) = LOWER('
                f'{quote_value(value)}'
                f')'
            )

        elif operator == "!=":

            condition = (
                f'LOWER(CAST('
                f'{quoted_column} AS TEXT'
                f')) != LOWER('
                f'{quote_value(value)}'
                f')'
            )

        else:

            condition = (
                f'{quoted_column} '
                f'{operator} '
                f'{quote_value(value)}'
            )

        where_parts.append(
            condition
        )

    if where_parts:

        sql += (
            "\nWHERE "
            + "\nAND ".join(
                where_parts
            )
        )

    # ========================================================
    # GROUP BY
    # ========================================================

    if group_by:

        sql += (
            "\nGROUP BY "
            + ", ".join(
                quote_identifier(column)
                for column in group_by
            )
        )

    # ========================================================
    # ORDER BY
    # ========================================================

    if sort_column:

        # If aggregation is used, order by the
        # aggregate result.
        if (
            aggregation != "NONE"
            and sort_column == metric_column
        ):

            sql += (
                "\nORDER BY result "
                + sort_direction
            )

        else:

            sql += (
                "\nORDER BY "
                + quote_identifier(
                    sort_column
                )
                + " "
                + sort_direction
            )

    # ========================================================
    # LIMIT
    # ========================================================

    if limit is not None:

        sql += (
            f"\nLIMIT {int(limit)}"
        )

    sql += ";"

    return sql