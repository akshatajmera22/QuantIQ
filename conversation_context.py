from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURATION
# ============================================================

MAX_CONVERSATION_MESSAGES = 8
MAX_CONTENT_LENGTH = 1500
MAX_SQL_LENGTH = 3000


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(
    value: Any,
    max_length: int = MAX_CONTENT_LENGTH,
) -> str:

    if value is None:
        return ""

    text = str(value).strip()

    if len(text) > max_length:
        text = (
            text[:max_length]
            + "..."
        )

    return text


# ============================================================
# BUILD CONVERSATION CONTEXT
# ============================================================

def build_conversation_context(
    conversation: Optional[
        List[Dict[str, Any]]
    ],
) -> str:
    """
    Convert recent frontend conversation messages into
    a compact context block for the Gemini planner.

    This function does NOT understand business-specific
    concepts.

    It does not hardcode:
        - dates
        - regions
        - customers
        - products
        - sales
        - countries
        - metrics

    It simply passes recent conversation information
    to Gemini so Gemini can resolve references such as:

        "that month"
        "that region"
        "those customers"
        "the same period"
        "it"
        "them"
    """

    if not conversation:
        return ""

    recent_messages = conversation[
        -MAX_CONVERSATION_MESSAGES:
    ]

    parts = []

    parts.append(
        "RECENT CONVERSATION"
    )

    parts.append(
        "==================="
    )

    valid_turn_count = 0

    for message in recent_messages:

        if not isinstance(
            message,
            dict,
        ):
            continue

        role = str(
            message.get(
                "role",
                "",
            )
        ).strip().lower()

        if role not in {
            "user",
            "assistant",
        }:
            continue

        content = clean_text(
            message.get(
                "content",
                "",
            )
        )

        if not content:
            continue

        valid_turn_count += 1

        parts.append(
            ""
        )

        parts.append(
            f"TURN {valid_turn_count} - "
            f"{role.upper()}"
        )

        parts.append(
            content
        )

        # ----------------------------------------------------
        # SQL FROM PREVIOUS ASSISTANT RESPONSE
        # ----------------------------------------------------

        sql = message.get(
            "sql"
        )

        if isinstance(
            sql,
            list,
        ):

            sql_text = "\n\n".join(
                str(item)
                for item in sql
                if item
            )

        elif isinstance(
            sql,
            str,
        ):

            sql_text = sql

        else:

            sql_text = ""

        sql_text = clean_text(
            sql_text,
            MAX_SQL_LENGTH,
        )

        if sql_text:

            parts.append(
                "GENERATED SQL:"
            )

            parts.append(
                sql_text
            )

    if valid_turn_count == 0:
        return ""

    # --------------------------------------------------------
    # REFERENCE RESOLUTION INSTRUCTION
    # --------------------------------------------------------

    parts.append(
        ""
    )

    parts.append(
        "CONVERSATION REFERENCE RULES:"
    )

    parts.append(
        "The current question may refer to information "
        "from previous turns."
    )

    parts.append(
        "Resolve references such as "
        "'that month', 'that region', "
        "'that country', 'those customers', "
        "'the same period', 'it', or 'them' "
        "using the previous conversation when "
        "the meaning is clear."
    )

    parts.append(
        "Do not invent missing context. "
        "If a reference cannot be resolved reliably, "
        "use the available database schema and ask "
        "for clarification only when necessary."
    )

    return "\n".join(
        parts
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    example_conversation = [
        {
            "role": "user",
            "content": (
                "What were the total sales "
                "in March 2026?"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Total sales in March 2026 "
                "were 125000."
            ),
            "sql": (
                "SELECT SUM(`Sales`) AS result "
                "FROM `sales` "
                "WHERE `OrderDate` >= '2026-03-01' "
                "AND `OrderDate` < '2026-04-01';"
            ),
        },
        {
            "role": "user",
            "content": (
                "List the top 5 salespeople "
                "for that month."
            ),
        },
    ]

    print(
        build_conversation_context(
            example_conversation
        )
    )