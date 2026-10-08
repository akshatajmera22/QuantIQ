import duckdb
from pathlib import Path


# ============================================================
# DUCKDB ENGINE
# ============================================================

def execute_query(
    database_path: str,
    sql: str
):
    """
    Execute SQL against the supplied database.

    Returns a list of dictionaries.
    """

    database_path = str(
        Path(database_path)
    )

    connection = duckdb.connect(
        database=database_path
    )

    try:

        result = connection.execute(
            sql
        )

        columns = [
            column[0]
            for column in result.description
        ]

        rows = result.fetchall()

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:

        connection.close()


def execute_queries(
    database_path: str,
    queries: list
):
    """
    Execute multiple generated SQL queries.

    Accepts either:

        [
            "SELECT ..."
        ]

    or:

        [
            {
                "analysis_index": 0,
                "sql": "SELECT ..."
            }
        ]
    """

    results = []

    for index, item in enumerate(
        queries
    ):

        if isinstance(item, dict):

            sql = item["sql"]

            analysis_index = item.get(
                "analysis_index",
                index
            )

        else:

            sql = item

            analysis_index = index

        rows = execute_query(
            database_path,
            sql
        )

        results.append(
            {
                "analysis_index": analysis_index,
                "sql": sql,
                "rows": rows,
                "row_count": len(rows),
            }
        )

    return results