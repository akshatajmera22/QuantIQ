# ============================================================
# QUANTIQ SECURITY CONFIGURATION
# ============================================================

from fnmatch import fnmatch
from typing import Dict, Any, Set


# ------------------------------------------------------------
# Explicit protected objects
# ------------------------------------------------------------

BLOCKED_TABLES: Set[str] = set()

BLOCKED_TABLE_PATTERNS = {
    "*password*",
    "*credential*",
    "*secret*",
    "*api_key*",
    "*apikey*",
    "*access_token*",
    "*refresh_token*",
    "*private_key*",
    "*authentication*",
    "*auth_token*",
}

# Example:
# BLOCKED_COLUMNS = {
#     "users": {"email", "phone"},
# }
BLOCKED_COLUMNS: Dict[str, Set[str]] = {}


# ------------------------------------------------------------
# Automatically protected sensitive columns
# ------------------------------------------------------------

SENSITIVE_COLUMN_PATTERNS = {
    "*password*",
    "*passwd*",
    "*passcode*",
    "*credential*",
    "*secret*",
    "*api_key*",
    "*apikey*",
    "*access_token*",
    "*refresh_token*",
    "*auth_token*",
    "*private_key*",
    "*secret_key*",
    "*encryption_key*",
    "*security_answer*",
    "*security_question*",
    "*cvv*",
    "*cvc*",
    "*card_number*",
    "*credit_card*",
    "*debit_card*",
    "*bank_account*",
    "*account_number*",
    "*routing_number*",
    "*pan_number*",
    "*aadhaar*",
    "*passport_number*",
    "*social_security*",
    "*ssn*",

    # Contact / direct-identifying information
    "*email*",
    "*e_mail*",
    "*phone*",
    "*mobile*",
    "*telephone*",
    "*tel*",
    "*cell_number*",
    "*contact_number*",
    "*whatsapp*",

    # Location / identity information
    "*address*",
    "*street_address*",
    "*home_address*",
    "*date_of_birth*",
    "*dob*",
}


# ------------------------------------------------------------
# Security switches
# ------------------------------------------------------------

AUTO_BLOCK_SENSITIVE_COLUMNS = True
ENFORCE_SQL_SECURITY = True
BLOCK_STAR_ON_PROTECTED_OBJECTS = True

# Without a full SQL parser/schema at every validation boundary, a projection
# wildcard can accidentally expose a sensitive column. QuantIQ therefore
# blocks SELECT * projections and expects generated SQL to name columns.
# COUNT(*) remains allowed.
BLOCK_ALL_SELECT_STAR = True


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_identifier(value: Any) -> str:
    """Normalize SQL identifiers for case-insensitive matching."""
    if value is None:
        return ""

    value = str(value).strip()

    # Remove common SQL identifier quoting.
    value = value.replace("`", "")
    value = value.replace('"', "")
    value = value.replace("[", "")
    value = value.replace("]", "")

    return value.strip().lower()


# ============================================================
# TABLE SECURITY
# ============================================================

def is_table_explicitly_blocked(table_name: str) -> bool:
    normalized = normalize_identifier(table_name)

    return normalized in {
        normalize_identifier(value)
        for value in BLOCKED_TABLES
    }


def is_table_pattern_blocked(table_name: str) -> bool:
    normalized = normalize_identifier(table_name)

    return any(
        fnmatch(normalized, normalize_identifier(pattern))
        for pattern in BLOCKED_TABLE_PATTERNS
    )


def is_table_blocked(table_name: str) -> bool:
    return (
        is_table_explicitly_blocked(table_name)
        or is_table_pattern_blocked(table_name)
    )


# ============================================================
# COLUMN SECURITY
# ============================================================

def is_column_explicitly_blocked(
    table_name: str,
    column_name: str,
) -> bool:
    table = normalize_identifier(table_name)
    column = normalize_identifier(column_name)

    # Global column blocks can be represented using an empty table key.
    blocked_for_table = BLOCKED_COLUMNS.get(table, set())
    blocked_global = BLOCKED_COLUMNS.get("", set())

    normalized_table_values = {
        normalize_identifier(value)
        for value in blocked_for_table
    }
    normalized_global_values = {
        normalize_identifier(value)
        for value in blocked_global
    }

    return (
        column in normalized_table_values
        or column in normalized_global_values
    )


def is_sensitive_column(column_name: str) -> bool:
    normalized = normalize_identifier(column_name)

    if not AUTO_BLOCK_SENSITIVE_COLUMNS:
        return False

    return any(
        fnmatch(normalized, normalize_identifier(pattern))
        for pattern in SENSITIVE_COLUMN_PATTERNS
    )


def is_column_blocked(
    table_name: str,
    column_name: str,
) -> bool:
    if is_table_blocked(table_name):
        return True

    return (
        is_column_explicitly_blocked(
            table_name,
            column_name,
        )
        or is_sensitive_column(column_name)
    )


# ============================================================
# SAFE SECURITY SUMMARY
# ============================================================

def get_security_summary() -> Dict[str, Any]:
    """Return security configuration without exposing secrets."""
    return {
        "blocked_table_count": len(BLOCKED_TABLES),
        "blocked_table_pattern_count": len(BLOCKED_TABLE_PATTERNS),
        "explicit_blocked_column_table_count": len(BLOCKED_COLUMNS),
        "sensitive_column_pattern_count": len(SENSITIVE_COLUMN_PATTERNS),
        "auto_block_sensitive_columns": AUTO_BLOCK_SENSITIVE_COLUMNS,
        "enforce_sql_security": ENFORCE_SQL_SECURITY,
        "block_star_on_protected_objects": BLOCK_STAR_ON_PROTECTED_OBJECTS,
        "block_all_select_star": BLOCK_ALL_SELECT_STAR,
    }
