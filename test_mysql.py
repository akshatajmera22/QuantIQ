from mysql_manager import test_and_connect_mysql
from mysql_engine import (
    list_databases,
    list_tables,
    build_schema_context,
)
from mysql_manager import get_mysql_connection


HOST = "localhost"
PORT = 3306
USERNAME = "root"
PASSWORD = "akshat@2004"


result = test_and_connect_mysql(
    host=HOST,
    port=PORT,
    username=USERNAME,
    password=PASSWORD,
)

print("\nCONNECTION RESULT")
print(result)


if result["success"]:

    connection = get_mysql_connection()

    print("\nDATABASES")

    databases = list_databases(
        connection
    )

    for database in databases:
        print(" -", database)

    # If you know your database name, put it here.
    # Otherwise leave it None and we'll select one later.

    DATABASE = "sakila"

    if DATABASE:

        from mysql_manager import (
            select_mysql_database
        )

        select_mysql_database(
            DATABASE
        )

        print("\nTABLES")

        tables = list_tables(
            connection,
            DATABASE
        )

        for table in tables:
            print(" -", table)

        print("\nSCHEMA")

        print(
            build_schema_context(
                connection,
                DATABASE
            )
        )