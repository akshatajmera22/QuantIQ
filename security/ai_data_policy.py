# ============================================================
# QUANTIQ AI DATA POLICY
# ============================================================
#
# Controls what database RESULT DATA is allowed to reach Gemini.
#
# IMPORTANT:
# This is separate from schema security.
#
# Schema security:
#     Protects database metadata sent to the planner.
#
# AI data policy:
#     Protects actual query results sent to Gemini.
#
# UI results are NOT affected by this policy.
# The frontend can still receive the verified database result.
# ============================================================


from typing import Dict, Any


# ============================================================
# AGGREGATE / KPI RESULTS
# ============================================================
#
# Examples:
#
# SUM(sales)
# AVG(profit)
# COUNT(*)
# MIN(...)
# MAX(...)
#
# These are generally safe for AI analysis as long as the
# underlying columns themselves are not sensitive.
# ============================================================

ALLOW_AGGREGATE_RESULTS = True


# ============================================================
# RAW ROW RESULTS
# ============================================================
#
# Default = False.
#
# This means Gemini does NOT automatically receive:
#
# customer rows
# employee rows
# transaction rows
# address rows
# email rows
# etc.
#
# The user can still see those rows in the QuantIQ UI.
# ============================================================

ALLOW_RAW_ROWS = False


# ============================================================
# SENSITIVE COLUMNS
# ============================================================
#
# Sensitive columns are detected using the existing security
# configuration.
# ============================================================

BLOCK_SENSITIVE_COLUMNS = True


# ============================================================
# RESULT SIZE LIMITS
# ============================================================

MAX_AI_ROWS = 20

MAX_AI_COLUMNS = 30

MAX_AI_RESULT_CHARACTERS = 12000


# ============================================================
# ERROR INFORMATION
# ============================================================
#
# Do not send raw database errors to Gemini because they may
# contain table names, paths, connection details, SQL fragments,
# or other internal information.
# ============================================================

SEND_DATABASE_ERROR_DETAILS = False


# ============================================================
# SECURITY SUMMARY
# ============================================================

def get_ai_data_policy_summary() -> Dict[str, Any]:
    """
    Return a frontend-safe summary of the AI data boundary.
    """

    return {
        "allow_aggregate_results": (
            ALLOW_AGGREGATE_RESULTS
        ),
        "allow_raw_rows": (
            ALLOW_RAW_ROWS
        ),
        "block_sensitive_columns": (
            BLOCK_SENSITIVE_COLUMNS
        ),
        "max_ai_rows": (
            MAX_AI_ROWS
        ),
        "max_ai_columns": (
            MAX_AI_COLUMNS
        ),
        "max_ai_result_characters": (
            MAX_AI_RESULT_CHARACTERS
        ),
        "send_database_error_details": (
            SEND_DATABASE_ERROR_DETAILS
        ),
    }