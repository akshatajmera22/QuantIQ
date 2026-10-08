"""
QuantIQ Context Selector

Purpose:
    Reduce the amount of schema information sent to Gemini
    while preserving all tables and foreign-key paths needed
    to answer the user's question.

Important:
    - No Gemini calls.
    - No dataset-specific table names.
    - No dataset-specific column names.
    - No dataset-specific questions.
    - No hardcoded answers.
    - Foreign-key relationships determine JOIN paths.
"""

from __future__ import annotations

import re

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple


# ============================================================
# CONFIGURATION
# ============================================================

MAX_SELECTED_TABLES = 12

MAX_SELECTED_COLUMNS_PER_TABLE = 30

MIN_TABLE_SCORE = 1


# ============================================================
# GENERIC ANALYTICAL VOCABULARY
# ============================================================

GENERIC_CONCEPTS = {

    "revenue": {
        "revenue",
        "revenues",
        "sales",
        "sale",
        "income",
        "earnings",
        "turnover",
        "money",
        "amount",
        "amounts",
        "payment",
        "payments",
        "price",
        "prices",
        "value",
        "values",
        "total",
    },

    "sales": {
        "sales",
        "sale",
        "revenue",
        "revenues",
        "income",
        "amount",
        "payment",
        "payments",
        "price",
        "value",
        "total",
    },

    "money": {
        "money",
        "revenue",
        "revenues",
        "sales",
        "sale",
        "income",
        "earnings",
        "amount",
        "payment",
        "payments",
        "price",
        "value",
        "total",
    },

    "profit": {
        "profit",
        "profits",
        "margin",
        "income",
        "revenue",
        "revenues",
        "sales",
        "sale",
        "cost",
        "costs",
        "amount",
    },

    "cost": {
        "cost",
        "costs",
        "expense",
        "expenses",
        "amount",
        "price",
        "value",
        "total",
    },

    "payment": {
        "payment",
        "payments",
        "amount",
        "amounts",
        "money",
        "value",
        "total",
    },

    "quantity": {
        "quantity",
        "qty",
        "count",
        "units",
        "unit",
        "number",
        "stock",
        "inventory",
        "available",
    },

    "price": {
        "price",
        "prices",
        "rate",
        "rates",
        "cost",
        "amount",
        "value",
        "total",
    },

    "customer": {
        "customer",
        "customers",
        "client",
        "clients",
        "buyer",
        "buyers",
    },

    "product": {
        "product",
        "products",
        "item",
        "items",
        "goods",
        "inventory",
    },

    "actor": {
        "actor",
        "actors",
        "performer",
        "performers",
        "person",
        "people",
    },

    "film": {
        "film",
        "films",
        "movie",
        "movies",
        "title",
        "titles",
    },

    "employee": {
        "employee",
        "employees",
        "staff",
        "worker",
        "workers",
        "salesperson",
        "salespeople",
    },

    "location": {
        "country",
        "countries",
        "city",
        "cities",
        "state",
        "states",
        "region",
        "regions",
        "location",
        "locations",
    },

    "date": {
        "date",
        "dates",
        "day",
        "month",
        "year",
        "week",
        "quarter",
        "period",
    },
}


# ============================================================
# GENERIC MEASURE WORDS
# ============================================================

GENERIC_MEASURE_WORDS = {
    "amount",
    "amounts",
    "price",
    "prices",
    "cost",
    "costs",
    "revenue",
    "revenues",
    "sales",
    "sale",
    "profit",
    "profits",
    "income",
    "value",
    "values",
    "total",
    "quantity",
    "qty",
    "count",
    "number",
    "rate",
    "rates",
    "population",
    "salary",
    "salaries",
    "payment",
    "payments",
    "discount",
    "discounts",
    "units",
    "stock",
    "inventory",
}


# ============================================================
# STOP WORDS
# ============================================================

GENERIC_STOP_WORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "for",
    "from",
    "with",
    "and",
    "or",
    "by",
    "in",
    "on",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "has",
    "have",
    "had",
    "that",
    "this",
    "those",
    "these",
    "all",
    "each",
    "every",
    "show",
    "display",
    "list",
    "find",
    "give",
    "get",
    "return",
    "tell",
    "me",
    "what",
    "which",
    "who",
    "how",
    "does",
    "do",
    "did",
    "can",
    "could",
    "would",
    "should",
    "please",
    "top",
    "bottom",
    "highest",
    "lowest",
    "most",
    "least",
    "best",
    "worst",
    "more",
    "less",
    "than",
    "over",
    "under",
    "above",
    "below",
    "greater",
    "lower",
    "higher",
    "only",
    "include",
    "generated",
    "brought",
    "into",
}


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(
    text: str,
) -> List[str]:

    if not text:
        return []

    text = str(
        text
    ).lower()

    tokens = re.findall(
        r"[a-zA-Z0-9_]+",
        text,
    )

    return [
        token
        for token in tokens
        if token
    ]


# ============================================================
# IDENTIFIER NORMALIZATION
# ============================================================

def normalize_identifier(
    value: str,
) -> str:

    if value is None:
        return ""

    value = str(
        value
    ).strip().lower()

    value = re.sub(
        r"([a-z0-9])([A-Z])",
        r"\1_\2",
        value,
    )

    value = re.sub(
        r"[^a-z0-9_]+",
        "_",
        value,
    )

    value = re.sub(
        r"_+",
        "_",
        value,
    )

    return value.strip(
        "_"
    )


# ============================================================
# IDENTIFIER TOKENS
# ============================================================

def identifier_tokens(
    value: str,
) -> Set[str]:

    normalized = normalize_identifier(
        value
    )

    if not normalized:
        return set()

    parts = normalized.split(
        "_"
    )

    tokens = set(
        parts
    )

    tokens.add(
        normalized
    )

    return tokens


# ============================================================
# SINGULARIZE
# ============================================================

def singularize(
    word: str,
) -> str:

    word = str(
        word
    ).lower().strip()

    if len(word) <= 3:
        return word

    if word.endswith(
        "ies"
    ):
        return word[:-3] + "y"

    if word.endswith(
        "ses"
    ):
        return word[:-2]

    if word.endswith(
        "xes"
    ):
        return word[:-2]

    if word.endswith(
        "zes"
    ):
        return word[:-2]

    if word.endswith(
        "ches"
    ):
        return word[:-2]

    if word.endswith(
        "shes"
    ):
        return word[:-2]

    if (
        word.endswith("s")
        and not word.endswith("ss")
    ):
        return word[:-1]

    return word


# ============================================================
# PLURALIZE
# ============================================================

def pluralize(
    word: str,
) -> str:

    word = str(
        word
    ).lower().strip()

    if not word:
        return word

    if word.endswith(
        "y"
    ) and len(word) > 2:

        return word[:-1] + "ies"

    if (
        word.endswith("s")
        or word.endswith("x")
        or word.endswith("z")
        or word.endswith("ch")
        or word.endswith("sh")
    ):

        return word + "es"

    return word + "s"


# ============================================================
# WORD MATCH
# ============================================================

def words_match(
    question_word: str,
    identifier_word: str,
) -> bool:

    q = singularize(
        question_word
    )

    i = singularize(
        identifier_word
    )

    if q == i:
        return True

    if pluralize(q) == identifier_word.lower():
        return True

    if pluralize(i) == question_word.lower():
        return True

    return False


# ============================================================
# QUESTION TOKEN EXPANSION
# ============================================================

def expand_question_tokens(
    question_tokens: List[str],
) -> Set[str]:

    expanded = set(
        question_tokens
    )

    for token in question_tokens:

        for concept_words in (
            GENERIC_CONCEPTS.values()
        ):

            if token in concept_words:

                expanded.update(
                    concept_words
                )

    return expanded


# ============================================================
# SCHEMA PARSER
# ============================================================

def parse_schema_context(
    schema_context: str,
) -> Tuple[
    Dict[str, List[Dict[str, str]]],
    List[Dict[str, str]],
]:

    tables: Dict[
        str,
        List[Dict[str, str]]
    ] = {}

    relationships: List[
        Dict[str, str]
    ] = []

    current_table = None

    if not schema_context:

        return (
            tables,
            relationships,
        )

    lines = schema_context.splitlines()

    in_relationships = False

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            continue

        # ====================================================
        # TABLE
        # ====================================================

        table_match = re.match(
            r'^TABLE:\s*"([^"]+)"',
            line,
            flags=re.IGNORECASE,
        )

        if table_match:

            current_table = (
                table_match.group(1)
            )

            tables.setdefault(
                current_table,
                [],
            )

            in_relationships = False

            continue

        # ====================================================
        # FOREIGN KEY SECTION
        # ====================================================

        if (
            line.upper()
            == "FOREIGN KEY RELATIONSHIPS:"
        ):

            in_relationships = True

            current_table = None

            continue

        # ====================================================
        # FOREIGN KEY
        # ====================================================

        if in_relationships:

            relationship_match = re.match(
                r'^-\s*"([^"]+)"\."([^"]+)"\s*->\s*"([^"]+)"\."([^"]+)"',
                line,
                flags=re.IGNORECASE,
            )

            if relationship_match:

                relationships.append(
                    {
                        "table":
                            relationship_match.group(1),

                        "column":
                            relationship_match.group(2),

                        "referenced_table":
                            relationship_match.group(3),

                        "referenced_column":
                            relationship_match.group(4),
                    }
                )

            continue

        # ====================================================
        # COLUMN
        # ====================================================

        if current_table:

            column_match = re.match(
                r'^-\s*"([^"]+)"\s*\((.*)\)',
                line,
            )

            if column_match:

                column_name = (
                    column_match.group(1)
                )

                column_type = (
                    column_match.group(2)
                )

                column_type = re.sub(
                    r"\s*\[[^\]]*\]\s*$",
                    "",
                    column_type,
                ).strip()

                tables[
                    current_table
                ].append(
                    {
                        "name":
                            column_name,

                        "type":
                            column_type,
                    }
                )

    return (
        tables,
        relationships,
    )


# ============================================================
# COLUMN TYPE HELPERS
# ============================================================

def is_numeric_type(
    column_type: str,
) -> bool:

    value = str(
        column_type or ""
    ).lower()

    base = value.split(
        "(",
        1
    )[0].strip()

    return base in {
        "int",
        "integer",
        "bigint",
        "smallint",
        "tinyint",
        "mediumint",
        "decimal",
        "numeric",
        "float",
        "double",
        "real",
        "serial",
        "bigserial",
    }


def is_date_type(
    column_type: str,
) -> bool:

    value = str(
        column_type or ""
    ).lower()

    base = value.split(
        "(",
        1
    )[0].strip()

    return base in {
        "date",
        "datetime",
        "timestamp",
        "time",
        "year",
    }


# ============================================================
# TABLE SCORING
# ============================================================

def score_table(
    question_tokens: List[str],
    table_name: str,
    columns: List[Dict[str, str]],
) -> Tuple[
    int,
    Set[str],
]:

    score = 0

    matched_columns: Set[str] = set()

    table_tokens = identifier_tokens(
        table_name
    )

    expanded_tokens = expand_question_tokens(
        question_tokens
    )

    # ========================================================
    # TABLE NAME MATCH
    # ========================================================

    for question_token in expanded_tokens:

        if (
            question_token
            in GENERIC_STOP_WORDS
        ):
            continue

        for table_token in table_tokens:

            if words_match(
                question_token,
                table_token,
            ):

                score += 10

                break

    # ========================================================
    # PARTIAL TABLE MATCH
    # ========================================================

    normalized_table = normalize_identifier(
        table_name
    )

    for question_token in expanded_tokens:

        if (
            question_token
            in GENERIC_STOP_WORDS
        ):
            continue

        normalized_question = normalize_identifier(
            question_token
        )

        if not normalized_question:
            continue

        if (
            normalized_question
            in normalized_table
            or normalized_table
            in normalized_question
        ):

            score += 5

    # ========================================================
    # COLUMN MATCH
    # ========================================================

    for column in columns:

        column_name = column.get(
            "name",
            "",
        )

        column_type = column.get(
            "type",
            "",
        )

        column_tokens = identifier_tokens(
            column_name
        )

        column_score = 0

        for question_token in expanded_tokens:

            if (
                question_token
                in GENERIC_STOP_WORDS
            ):
                continue

            for column_token in column_tokens:

                if words_match(
                    question_token,
                    column_token,
                ):

                    column_score += 4

                    break

        if column_score > 0:

            score += min(
                column_score,
                12,
            )

            matched_columns.add(
                column_name
            )

        # ====================================================
        # GENERIC NUMERIC MEASURE
        # ====================================================

        if (
            is_numeric_type(
                column_type
            )
            and any(
                token in GENERIC_MEASURE_WORDS
                for token in expanded_tokens
            )
        ):

            normalized_column = normalize_identifier(
                column_name
            )

            column_words = set(
                normalized_column.split("_")
            )

            if (
                column_words
                & GENERIC_MEASURE_WORDS
            ):

                score += 5

                matched_columns.add(
                    column_name
                )

        # ====================================================
        # GENERIC DATE
        # ====================================================

        if (
            is_date_type(
                column_type
            )
            and any(
                token in {
                    "date",
                    "month",
                    "year",
                    "day",
                    "period",
                    "quarter",
                    "week",
                }
                for token in expanded_tokens
            )
        ):

            score += 3

            matched_columns.add(
                column_name
            )

    return (
        score,
        matched_columns,
    )


# ============================================================
# RELATIONSHIP GRAPH
# ============================================================

def build_relationship_graph(
    relationships: List[
        Dict[str, str]
    ],
) -> Dict[
    str,
    Set[str]
]:

    graph: Dict[
        str,
        Set[str]
    ] = defaultdict(set)

    for relationship in relationships:

        left = relationship.get(
            "table"
        )

        right = relationship.get(
            "referenced_table"
        )

        if not left or not right:
            continue

        graph[
            left
        ].add(
            right
        )

        graph[
            right
        ].add(
            left
        )

    return graph


# ============================================================
# SHORTEST PATH BETWEEN TABLES
# ============================================================

def find_shortest_path(
    graph: Dict[
        str,
        Set[str]
    ],
    start: str,
    target: str,
) -> List[str]:

    if start == target:
        return [start]

    queue = deque()

    queue.append(
        (
            start,
            [start],
        )
    )

    visited = {
        start
    }

    while queue:

        current, path = (
            queue.popleft()
        )

        for neighbor in sorted(
            graph.get(
                current,
                set(),
            )
        ):

            if neighbor in visited:
                continue

            new_path = (
                path
                + [neighbor]
            )

            if neighbor == target:

                return new_path

            visited.add(
                neighbor
            )

            queue.append(
                (
                    neighbor,
                    new_path,
                )
            )

    return []


# ============================================================
# CONNECT SELECTED TABLES
# ============================================================

def connect_selected_tables(
    selected_tables: Set[str],
    graph: Dict[
        str,
        Set[str]
    ],
    max_tables: int,
) -> Set[str]:

    """
    CRITICAL FUNCTION.

    If the planner needs two relevant tables, preserve the
    complete foreign-key path between them.

    Example:

        film
          |
        inventory
          |
        rental
          |
        payment

    If `film` and `payment` are selected, this function adds:

        inventory
        rental

    automatically.

    Nothing here knows that these are Sakila tables.
    It works entirely from the FK graph.
    """

    selected = set(
        selected_tables
    )

    if len(selected) <= 1:
        return selected

    selected_list = list(
        selected
    )

    # --------------------------------------------------------
    # Connect every pair of selected tables.
    # --------------------------------------------------------

    paths = []

    for index in range(
        len(selected_list)
    ):

        for j in range(
            index + 1,
            len(selected_list),
        ):

            left = selected_list[
                index
            ]

            right = selected_list[
                j
            ]

            path = find_shortest_path(
                graph=graph,
                start=left,
                target=right,
            )

            if path:

                paths.append(
                    (
                        len(path),
                        left,
                        right,
                        path,
                    )
                )

    # --------------------------------------------------------
    # Shortest paths first.
    # --------------------------------------------------------

    paths.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    for (
        _,
        _,
        _,
        path,
    ) in paths:

        for table_name in path:

            # Never remove an already selected table.

            if table_name in selected:
                continue

            if (
                len(selected)
                >= max_tables
            ):

                return selected

            selected.add(
                table_name
            )

    return selected


# ============================================================
# RELATIONSHIPS FOR SELECTED TABLES
# ============================================================

def relationships_for_tables(
    relationships: List[
        Dict[str, str]
    ],
    selected_tables: Set[str],
) -> List[
    Dict[str, str]
]:

    selected = set(
        selected_tables
    )

    output = []

    for relationship in relationships:

        left = relationship.get(
            "table"
        )

        right = relationship.get(
            "referenced_table"
        )

        if (
            left in selected
            and right in selected
        ):

            output.append(
                relationship
            )

    return output


# ============================================================
# SELECT RELEVANT TABLES
# ============================================================

def select_relevant_tables(
    tables: Dict[
        str,
        List[Dict[str, str]]
    ],
    relationships: List[
        Dict[str, str]
    ],
    question: str,
    max_tables: int,
) -> Tuple[
    Set[str],
    Dict[str, Set[str]],
    Dict[str, int],
]:

    question_tokens = tokenize(
        question
    )

    table_scores = {}

    matched_columns_by_table = {}

    # ========================================================
    # SCORE ALL TABLES
    # ========================================================

    for (
        table_name,
        columns,
    ) in tables.items():

        score, matched_columns = (
            score_table(
                question_tokens,
                table_name,
                columns,
            )
        )

        table_scores[
            table_name
        ] = score

        matched_columns_by_table[
            table_name
        ] = matched_columns

    # ========================================================
    # RANK TABLES
    # ========================================================

    ranked_tables = sorted(
        table_scores.items(),
        key=lambda item: (
            item[1],
            len(
                matched_columns_by_table[
                    item[0]
                ]
            ),
        ),
        reverse=True,
    )

    selected_tables: Set[str] = set()

    # ========================================================
    # SELECT DIRECTLY RELEVANT TABLES
    # ========================================================

    for (
        table_name,
        score,
    ) in ranked_tables:

        if score < MIN_TABLE_SCORE:
            continue

        selected_tables.add(
            table_name
        )

        # We intentionally leave some capacity for
        # relationship-path tables.
        #
        # Example:
        #
        # film + payment
        #
        # must still have room for:
        #
        # inventory + rental

        direct_limit = min(
            6,
            max_tables,
        )

        if (
            len(selected_tables)
            >= direct_limit
        ):

            break

    # ========================================================
    # FALLBACK
    # ========================================================

    if not selected_tables:

        if ranked_tables:

            selected_tables.add(
                ranked_tables[0][0]
            )

    # ========================================================
    # BUILD GRAPH
    # ========================================================

    graph = build_relationship_graph(
        relationships
    )

    # ========================================================
    # CRITICAL:
    # CONNECT DIRECTLY SELECTED TABLES
    # ========================================================

    selected_tables = connect_selected_tables(
        selected_tables=selected_tables,
        graph=graph,
        max_tables=max_tables,
    )

    # ========================================================
    # GENERIC METRIC DETECTION
    # ========================================================

    expanded_tokens = expand_question_tokens(
        question_tokens
    )

    metric_requested = any(
        token in GENERIC_MEASURE_WORDS
        or token in {
            "revenue",
            "money",
            "sales",
            "profit",
            "payment",
            "payments",
            "amount",
            "quantity",
            "price",
            "cost",
        }
        for token in expanded_tokens
    )

    # ========================================================
    # FIND POTENTIAL METRIC TABLES
    # ========================================================

    if metric_requested:

        metric_candidates = []

        for (
            table_name,
            columns,
        ) in tables.items():

            numeric_columns = [
                column
                for column in columns
                if is_numeric_type(
                    column.get(
                        "type",
                        "",
                    )
                )
            ]

            if not numeric_columns:
                continue

            measure_column_count = 0

            for column in numeric_columns:

                normalized_column = normalize_identifier(
                    column.get(
                        "name",
                        "",
                    )
                )

                column_words = set(
                    normalized_column.split("_")
                )

                if (
                    column_words
                    & GENERIC_MEASURE_WORDS
                ):

                    measure_column_count += 1

            metric_candidates.append(
                (
                    table_name,
                    table_scores.get(
                        table_name,
                        0,
                    ),
                    measure_column_count,
                )
            )

        metric_candidates.sort(
            key=lambda item: (
                item[2],
                item[1],
            ),
            reverse=True,
        )

        # ----------------------------------------------------
        # Only add metric candidates when they are connected
        # to already relevant tables.
        # ----------------------------------------------------

        for (
            metric_table,
            _,
            _,
        ) in metric_candidates:

            if (
                metric_table
                in selected_tables
            ):
                continue

            if (
                len(selected_tables)
                >= max_tables
            ):
                break

            # Find shortest path from any selected table.
            best_path = None

            for selected_table in list(
                selected_tables
            ):

                path = find_shortest_path(
                    graph=graph,
                    start=selected_table,
                    target=metric_table,
                )

                if not path:
                    continue

                if (
                    best_path is None
                    or len(path)
                    < len(best_path)
                ):

                    best_path = path

            if best_path:

                for table_name in best_path:

                    if (
                        len(selected_tables)
                        >= max_tables
                    ):
                        break

                    selected_tables.add(
                        table_name
                    )

    # ========================================================
    # CONNECT AGAIN
    # ========================================================

    # Adding a metric table may introduce another disconnected
    # relevant table, so run path preservation again.

    selected_tables = connect_selected_tables(
        selected_tables=selected_tables,
        graph=graph,
        max_tables=max_tables,
    )

    # ========================================================
    # FINAL PRIORITY
    # ========================================================

    if (
        len(selected_tables)
        > max_tables
    ):

        priority = []

        for table_name in selected_tables:

            score = table_scores.get(
                table_name,
                0,
            )

            direct_columns = len(
                matched_columns_by_table.get(
                    table_name,
                    set(),
                )
            )

            priority.append(
                (
                    score,
                    direct_columns,
                    table_name,
                )
            )

        priority.sort(
            reverse=True
        )

        selected_tables = {
            item[2]
            for item in priority[
                :max_tables
            ]
        }

    return (
        selected_tables,
        matched_columns_by_table,
        table_scores,
    )


# ============================================================
# BUILD REDUCED CONTEXT
# ============================================================

def build_reduced_context(
    schema_context: str,
    question: str,
    max_tables: int = MAX_SELECTED_TABLES,
) -> str:

    if not schema_context:
        return ""

    tables, relationships = (
        parse_schema_context(
            schema_context
        )
    )

    # ========================================================
    # PARSER FALLBACK
    # ========================================================

    if not tables:

        return schema_context

    (
        selected_tables,
        matched_columns_by_table,
        _,
    ) = select_relevant_tables(
        tables=tables,
        relationships=relationships,
        question=question,
        max_tables=max_tables,
    )

    # ========================================================
    # PRESERVE ORIGINAL TABLE ORDER
    # ========================================================

    ordered_selected_tables = [
        table_name
        for table_name in tables.keys()
        if table_name in selected_tables
    ]

    # ========================================================
    # OUTPUT
    # ========================================================

    output = []

    # --------------------------------------------------------
    # DATABASE / DIALECT
    # --------------------------------------------------------

    for line in schema_context.splitlines():

        stripped = line.strip()

        if (
            stripped.startswith(
                "DATABASE:"
            )
            or stripped.startswith(
                "DIALECT:"
            )
        ):

            output.append(
                stripped
            )

    output.append("")

    output.append(
        "RELEVANT TABLES:"
    )

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    for table_name in (
        ordered_selected_tables
    ):

        output.append("")

        output.append(
            f'TABLE: "{table_name}"'
        )

        columns = tables[
            table_name
        ]

        matched_columns = (
            matched_columns_by_table.get(
                table_name,
                set(),
            )
        )

        # Matched columns first, then remaining columns.
        #
        # We still retain the complete schema because JOIN
        # generation may need primary/foreign key columns.

        ordered_columns = sorted(
            columns,
            key=lambda column: (
                column.get(
                    "name",
                    ""
                )
                not in matched_columns
            ),
        )

        for column in ordered_columns:

            column_name = column.get(
                "name",
                "",
            )

            column_type = column.get(
                "type",
                "",
            )

            output.append(
                f'- "{column_name}" '
                f'({column_type})'
            )

    # --------------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------------

    selected_relationships = (
        relationships_for_tables(
            relationships=relationships,
            selected_tables=selected_tables,
        )
    )

    output.append("")

    output.append(
        "FOREIGN KEY RELATIONSHIPS:"
    )

    if selected_relationships:

        for relationship in (
            selected_relationships
        ):

            output.append(
                f'- "{relationship["table"]}".'
                f'"{relationship["column"]}" '
                f'-> '
                f'"{relationship["referenced_table"]}".'
                f'"{relationship["referenced_column"]}"'
            )

    else:

        output.append(
            "- None detected"
        )

    return "\n".join(
        output
    )


# ============================================================
# PUBLIC API
# ============================================================

def select_context(
    question: str,
    schema_context: str,
    max_tables: int = MAX_SELECTED_TABLES,
) -> str:

    return build_reduced_context(
        schema_context=schema_context,
        question=question,
        max_tables=max_tables,
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    example_schema = """
DATABASE: sakila
DIALECT: MySQL

TABLE: "film"
- "film_id" (smallint unsigned)
- "title" (varchar(128))
- "description" (text)

TABLE: "inventory"
- "inventory_id" (mediumint unsigned)
- "film_id" (smallint unsigned)
- "store_id" (tinyint unsigned)

TABLE: "rental"
- "rental_id" (int)
- "rental_date" (datetime)
- "inventory_id" (mediumint unsigned)
- "customer_id" (smallint unsigned)

TABLE: "payment"
- "payment_id" (smallint unsigned)
- "customer_id" (smallint unsigned)
- "staff_id" (tinyint unsigned)
- "rental_id" (int)
- "amount" (decimal(5,2))
- "payment_date" (datetime)

TABLE: "customer"
- "customer_id" (smallint unsigned)
- "first_name" (varchar(45))
- "last_name" (varchar(45))

FOREIGN KEY RELATIONSHIPS:
- "inventory"."film_id" -> "film"."film_id"
- "rental"."inventory_id" -> "inventory"."inventory_id"
- "rental"."customer_id" -> "customer"."customer_id"
- "payment"."customer_id" -> "customer"."customer_id"
- "payment"."rental_id" -> "rental"."rental_id"
"""

    question = (
        "Find the top 3 film titles that brought "
        "in the most money, but only include films "
        "that have generated more than $200 in "
        "total revenue."
    )

    print()
    print("=" * 70)
    print("QUESTION")
    print("=" * 70)
    print(question)

    print()
    print("=" * 70)
    print("REDUCED CONTEXT")
    print("=" * 70)

    print(
        select_context(
            question=question,
            schema_context=example_schema,
        )
    )