from sqlalchemy import text


def validate_sql(engine, sql):
    """
    Checks whether SQL can be executed without actually
    modifying the database.
    """

    try:
        with engine.connect() as connection:

            # SQLite EXPLAIN validates the query syntax
            connection.execute(
                text(f"EXPLAIN QUERY PLAN {sql}")
            )

        return {
            "valid": True,
            "error": None
        }

    except Exception as error:

        return {
            "valid": False,
            "error": str(error)
        }