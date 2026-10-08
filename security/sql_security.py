# ============================================================
# QUANTIQ SQL SECURITY
# ============================================================

import re
from typing import Any, Dict, List

from security.security_config import (
    BLOCK_STAR_ON_PROTECTED_OBJECTS,
    BLOCK_ALL_SELECT_STAR,
    ENFORCE_SQL_SECURITY,
    is_column_blocked,
    is_sensitive_column,
    is_table_blocked,
    normalize_identifier,
)


# ============================================================
# SQL TEXT CLEANING
# ============================================================

def _strip_sql_literals_and_comments(sql: str) -> str:
    """
    Remove quoted string literals and SQL comments before security
    inspection so text such as 'password' cannot trigger or bypass
    identifier checks.
    """
    text = sql

    # SQL line comments.
    text = re.sub(r"--[^\n\r]*", " ", text)
    text = re.sub(r"#[^\n\r]*", " ", text)

    # SQL block comments.
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)

    # Single-quoted strings, including escaped single quotes.
    text = re.sub(r"'(?:''|\\'|[^'])*'", " ", text)

    # Double-quoted strings are ambiguous between strings and identifiers.
    # Keep their contents because MySQL/DuckDB commonly use double quotes
    # for identifiers. Identifier normalization handles the quote removal.

    return text


# ============================================================
# TABLE EXTRACTION
# ============================================================

_TABLE_REFERENCE_RE = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO|DELETE\s+FROM|MERGE\s+INTO)\s+"
    r"([`\"\[]?[A-Za-z_][A-Za-z0-9_$\- .]*[`\"\]]?)",
    re.IGNORECASE,
)


def _clean_table_reference(value: str) -> str:
    value = value.strip()

    # Stop at SQL punctuation/keywords that cannot belong to a table name.
    value = re.split(
        r"\s+(?:AS|ON|USING|WHERE|GROUP|ORDER|LIMIT|HAVING|UNION|LEFT|RIGHT|INNER|OUTER|FULL|CROSS)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    value = value.rstrip(";,)")
    return value.strip()


def _extract_table_references(sql: str) -> List[str]:
    cleaned = _strip_sql_literals_and_comments(sql)
    tables: List[str] = []

    for match in _TABLE_REFERENCE_RE.finditer(cleaned):
        table = _clean_table_reference(match.group(1))
        if table:
            tables.append(table)

    return tables


# ============================================================
# COLUMN EXTRACTION
# ============================================================

_QUALIFIED_COLUMN_RE = re.compile(
    r"(?:[`\"\[]?([A-Za-z_][A-Za-z0-9_$\-]*)[`\"\]]?)\s*\.\s*"
    r"(?:[`\"\[]?([A-Za-z_][A-Za-z0-9_$\-]*)[`\"\]]?)",
    re.IGNORECASE,
)

_TABLE_STAR_RE = re.compile(
    r"(?:[`\"\[]?([A-Za-z_][A-Za-z0-9_$\-]*)[`\"\]]?)\s*\.\s*\*",
    re.IGNORECASE,
)


_IDENTIFIER_RE = re.compile(
    r"[`\"]?([A-Za-z_][A-Za-z0-9_$\-]*)[`\"]?"
)


_SQL_KEYWORDS = {
    "select", "from", "where", "and", "or", "not", "as", "on", "join",
    "left", "right", "inner", "outer", "full", "cross", "group", "by",
    "order", "limit", "offset", "having", "union", "all", "distinct",
    "case", "when", "then", "else", "end", "asc", "desc", "null", "is",
    "in", "like", "between", "over", "partition", "rows", "range", "with",
    "recursive", "exists", "update", "into", "delete", "insert", "values",
    "set", "create", "alter", "drop", "truncate", "grant", "revoke",
    "true", "false", "interval", "current_date", "current_timestamp",
}


def _extract_qualified_columns(sql: str) -> List[tuple[str, str]]:
    cleaned = _strip_sql_literals_and_comments(sql)
    return [
        (match.group(1), match.group(2))
        for match in _QUALIFIED_COLUMN_RE.finditer(cleaned)
    ]


def _extract_unqualified_sensitive_identifiers(sql: str) -> List[str]:
    """
    Fail closed for sensitive column names even when the SQL uses an
    unqualified column reference, e.g. `SELECT password FROM users`.

    We inspect identifiers after removing comments and string literals.
    This is intentionally conservative: a name matching a protected
    pattern is blocked rather than relying on SQL parser-specific behavior.
    """
    cleaned = _strip_sql_literals_and_comments(sql)
    found: List[str] = []

    for match in _IDENTIFIER_RE.finditer(cleaned):
        identifier = match.group(1)
        normalized = normalize_identifier(identifier)

        if not normalized or normalized in _SQL_KEYWORDS:
            continue

        if is_sensitive_column(normalized):
            found.append(identifier)

    return found


# ============================================================
# VALIDATION
# ============================================================

def validate_sql_security(sql: str) -> Dict[str, Any]:
    """
    Validate a SQL statement against QuantIQ's protected data policy.

    This validator is intentionally fail-closed for protected table names,
    protected column names, and SELECT * against protected objects.
    """
    if not ENFORCE_SQL_SECURITY:
        return {
            "valid": True,
            "message": "SQL security enforcement is disabled.",
        }

    if not isinstance(sql, str) or not sql.strip():
        return {
            "valid": False,
            "message": "SQL query is empty.",
        }

    cleaned = _strip_sql_literals_and_comments(sql).strip()

    # Multiple statements are not required by QuantIQ's generated SQL path.
    # Reject them to prevent statement-chaining bypasses.
    if ";" in cleaned.rstrip(";"):
        return {
            "valid": False,
            "message": "Multiple SQL statements are not allowed.",
        }

    # Dangerous write/DDL statements are blocked.
    if re.match(
        r"^(DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|INSERT|UPDATE|DELETE|REPLACE|CALL|LOAD)\b",
        cleaned,
        re.IGNORECASE,
    ):
        return {
            "valid": False,
            "message": "This SQL operation is not allowed by QuantIQ security policy.",
        }

    # QuantIQ query paths must be read-only SELECT/WITH queries.
    if not re.match(r"^(SELECT|WITH)\b", cleaned, re.IGNORECASE):
        return {
            "valid": False,
            "message": "Only read-only SELECT queries are allowed.",
        }

    # Protected tables.
    for table in _extract_table_references(cleaned):
        if is_table_blocked(table):
            return {
                "valid": False,
                "message": (
                    f"Access to protected table '{table}' is blocked."
                ),
            }

    # Protected qualified columns.
    for table, column in _extract_qualified_columns(cleaned):
        if column == "*":
            continue

        if is_column_blocked(table, column):
            return {
                "valid": False,
                "message": (
                    f"Access to protected column '{column}' is blocked."
                ),
            }

    # Projection wildcards are blocked globally because a table that is not
    # itself protected may still contain a sensitive column such as password.
    # COUNT(*) and similar aggregate/function wildcards are intentionally not
    # blocked by this projection check.
    if BLOCK_ALL_SELECT_STAR:
        if re.search(
            r"(?:\bSELECT\b|,)\s*(?:[A-Za-z_][A-Za-z0-9_$\-]*\s*\.\s*)?\*",
            cleaned,
            re.IGNORECASE,
        ):
            return {
                "valid": False,
                "message": "SELECT * projections are blocked by QuantIQ security policy.",
            }

    # Protected table.*
    if BLOCK_STAR_ON_PROTECTED_OBJECTS:
        for table in _TABLE_STAR_RE.findall(cleaned):
            if is_table_blocked(table):
                return {
                    "valid": False,
                    "message": (
                        f"SELECT * from protected table '{table}' is blocked."
                    ),
                }

    # Unqualified sensitive columns.
    sensitive_identifiers = _extract_unqualified_sensitive_identifiers(cleaned)
    if sensitive_identifiers:
        identifier = sensitive_identifiers[0]
        return {
            "valid": False,
            "message": (
                f"Access to protected column '{identifier}' is blocked."
            ),
        }

    return {
        "valid": True,
        "message": "SQL passed QuantIQ security validation.",
    }


# ============================================================
# PUBLIC HELPERS
# ============================================================

def validate_generated_queries(
    queries: List[Dict[str, Any]],
) -> bool:
    """Validate every generated SQL query and raise on the first violation."""
    if not isinstance(queries, list) or not queries:
        raise ValueError("No generated SQL queries were provided.")

    for index, item in enumerate(queries):
        if not isinstance(item, dict):
            raise ValueError(
                f"Generated query {index} has an invalid structure."
            )

        sql = item.get("sql")
        validation = validate_sql_security(sql)

        if not validation.get("valid", False):
            raise PermissionError(
                f"Query {index} blocked by QuantIQ security: "
                f"{validation.get('message', 'Security validation failed.')}"
            )

    return True
