from mysql_manager import (
    test_and_connect_mysql,
    get_mysql_connection,
    get_active_connection_info,
)

from mysql_engine import execute_query


# ============================================================
# MYSQL CONNECTION DETAILS
# ============================================================

HOST = "localhost"
PORT = 3306
USERNAME = "root"
PASSWORD = "akshat@2004"
DATABASE = "sakila"


# ============================================================
# CONNECT
# ============================================================

print()
print("CONNECTING TO MYSQL")
print("=" * 60)

connection_result = test_and_connect_mysql(
    host=HOST,
    port=PORT,
    username=USERNAME,
    password=PASSWORD,
    database=DATABASE,
)

print(connection_result)


if not connection_result.get("success"):
    print()
    print("MYSQL CONNECTION FAILED")
    raise SystemExit(1)


# ============================================================
# ACTIVE CONNECTION
# ============================================================

print()
print("ACTIVE CONNECTION")
print("=" * 60)

print(get_active_connection_info())


# ============================================================
# TEST QUERY
# ============================================================

sql = """
SELECT
    SUM(`amount`) AS result
FROM
    `payment`;
"""


print()
print("EXECUTING SQL")
print("=" * 60)

print(sql)


# ============================================================
# EXECUTE
# ============================================================

try:

    result = execute_query(
        connection=get_mysql_connection(),
        sql=sql,
    )

    print()
    print("MYSQL RESULT")
    print("=" * 60)

    print(result)

except Exception as exc:

    print()
    print("MYSQL QUERY FAILED")
    print("=" * 60)

    print(str(exc))


print()
print("=" * 60)
print("TEST COMPLETE")