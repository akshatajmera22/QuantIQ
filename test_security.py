# ============================================================
# QUANTIQ SECURITY REGRESSION TESTS
# ============================================================

from security.security_config import is_column_blocked, is_table_blocked
from security.sql_security import validate_sql_security


ALLOWED_QUERIES = [
    'SELECT SUM("Sales") FROM "Sample_Superstore"',
    'SELECT "Customer Name" FROM "Sample_Superstore"',
    'SELECT "Region", SUM("Sales") FROM "Sample_Superstore" GROUP BY "Region"',
    'SELECT COUNT(*) FROM "Sample_Superstore"',
]

BLOCKED_QUERIES = [
    'SELECT password FROM users',
    'SELECT users.password FROM users',
    'SELECT api_key FROM config',
    'SELECT access_token FROM sessions',
    'SELECT secret_key FROM config',
    'SELECT mobile_number FROM customers',
    'SELECT customers.mobile_number FROM customers',
    'SELECT phone FROM customers',
    'SELECT email FROM customers',
    'SELECT address FROM customers',
    'SELECT * FROM users',
    'SELECT users.* FROM users',
    'SELECT * FROM password_store',
    'DROP TABLE users',
    'UPDATE users SET password = \'x\'',
    'DELETE FROM users',
]


def assert_valid(sql: str) -> None:
    result = validate_sql_security(sql)
    assert result.get("valid") is True, f"Expected ALLOWED but got: {sql}\n{result}"


def assert_blocked(sql: str) -> None:
    result = validate_sql_security(sql)
    assert result.get("valid") is False, f"Expected BLOCKED but got: {sql}\n{result}"


for sql in ALLOWED_QUERIES:
    assert_valid(sql)

for sql in BLOCKED_QUERIES:
    assert_blocked(sql)

# Direct column-level checks used by schema/result security.
assert is_column_blocked("customers", "mobile_number")
assert is_column_blocked("customers", "phone")
assert is_column_blocked("customers", "email")
assert is_column_blocked("customers", "address")
assert is_column_blocked("users", "password")
assert is_column_blocked("config", "api_key")
assert is_column_blocked("sessions", "access_token")

print("QuantIQ security regression tests: PASS")
print(f"Allowed tests: {len(ALLOWED_QUERIES)}")
print(f"Blocked tests: {len(BLOCKED_QUERIES)}")
