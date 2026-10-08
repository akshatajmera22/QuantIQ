import json
import os
import re
import subprocess


MODEL_NAME = "llama3.1:8b"


# ============================================================
# OLLAMA
# ============================================================

def ask_ollama(prompt):
    env = os.environ.copy()

    # Use CPU because your CUDA setup previously failed.
    env["OLLAMA_NUM_GPU"] = "0"

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL_NAME],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env=env,
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Ollama timed out while creating the query plan."
        )

    except FileNotFoundError:
        raise RuntimeError(
            "Ollama was not found. Make sure Ollama is installed."
        )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr
            or result.stdout
            or "Ollama failed."
        )

    output = result.stdout.strip()

    if not output:
        raise RuntimeError(
            "Ollama returned an empty response."
        )

    return output


# ============================================================
# ROBUST JSON PARSER
# ============================================================

def clean_json(text):
    text = str(text).strip()

    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("```", "").strip()

    start = text.find("{")

    if start == -1:
        raise ValueError(
            "Planner did not return a JSON object."
        )

    text = text[start:]

    try:
        decoder = json.JSONDecoder()

        result, _ = decoder.raw_decode(text)

        return result

    except json.JSONDecodeError:
        pass

    repaired = []

    inside_string = False
    escaped = False

    for char in text:

        if escaped:
            repaired.append(char)
            escaped = False
            continue

        if char == "\\" and inside_string:
            repaired.append(char)
            escaped = True
            continue

        if char == '"':
            inside_string = not inside_string
            repaired.append(char)
            continue

        if char == "\n" and inside_string:
            repaired.append("\\n")
            continue

        if char == "\r" and inside_string:
            repaired.append("\\r")
            continue

        if char == "\t" and inside_string:
            repaired.append("\\t")
            continue

        if ord(char) < 32 and inside_string:
            repaired.append(" ")
            continue

        repaired.append(char)

    repaired_text = "".join(repaired)

    try:
        decoder = json.JSONDecoder()

        result, _ = decoder.raw_decode(
            repaired_text
        )

        return result

    except json.JSONDecodeError as exc:

        last_brace = repaired_text.rfind("}")

        if last_brace != -1:

            candidate = repaired_text[
                :last_brace + 1
            ]

            try:
                return json.loads(candidate)

            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Invalid planner JSON: {exc}"
        )


# ============================================================
# TABLE EXTRACTION
# ============================================================

def extract_tables(schema):

    if not schema:
        return []

    tables = re.findall(
        r'TABLE:\s*"([^"]+)"',
        str(schema),
        flags=re.IGNORECASE,
    )

    if not tables:

        tables = re.findall(
            r"TABLE:\s*([^\n]+)",
            str(schema),
            flags=re.IGNORECASE,
        )

    return list(
        dict.fromkeys(
            table.strip()
            for table in tables
            if table.strip()
        )
    )


# ============================================================
# DATABASE VALUES
# ============================================================

def build_values_context(database_values):

    if not database_values:
        return "(No categorical values supplied.)"

    parts = []

    if isinstance(database_values, dict):

        for table, columns in database_values.items():

            if not isinstance(columns, dict):
                continue

            for column, values in columns.items():

                if not values:
                    continue

                values = list(values)[:50]

                parts.append(
                    f'{table}.{column}: '
                    + ", ".join(
                        str(value)
                        for value in values
                    )
                )

    if not parts:
        return "(No categorical values supplied.)"

    return "\n".join(parts)


# ============================================================
# SEMANTIC CONTEXT
# ============================================================

def build_semantic_context(semantic_context):

    if not semantic_context:
        return "(No semantic analysis supplied.)"

    if isinstance(semantic_context, str):
        return semantic_context

    return json.dumps(
        semantic_context,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


# ============================================================
# EMPTY PLAN
# ============================================================

def empty_plan():

    return {
        "intent": "select",
        "table": "",
        "filters": [],
        "metric": {
            "column": "",
            "aggregation": "NONE",
        },
        "group_by": [],
        "sort": {
            "column": "",
            "direction": "ASC",
        },
        "limit": None,
    }


# ============================================================
# NORMALIZE PLAN
# ============================================================

def normalize_plan(plan):

    if not isinstance(plan, dict):
        plan = {}

    result = empty_plan()

    # --------------------------------------------------------
    # Intent
    # --------------------------------------------------------

    intent = str(
        plan.get("intent", "select")
        or "select"
    ).lower().strip()

    if intent not in {
        "select",
        "count",
        "aggregate",
        "ranking",
    }:
        intent = "select"

    result["intent"] = intent

    # --------------------------------------------------------
    # Table
    # --------------------------------------------------------

    result["table"] = str(
        plan.get("table", "")
        or ""
    ).strip()

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------

    filters = plan.get("filters", [])

    if not isinstance(filters, list):
        filters = []

    for item in filters:

        if not isinstance(item, dict):
            continue

        column = str(
            item.get("column", "")
            or ""
        ).strip()

        if not column:
            continue

        operator = str(
            item.get("operator", "=")
            or "="
        ).upper().strip()

        if operator not in {
            "=",
            "!=",
            ">",
            "<",
            ">=",
            "<=",
            "LIKE",
        }:
            operator = "="

        result["filters"].append(
            {
                "column": column,
                "operator": operator,
                "value": item.get("value"),
            }
        )

    # --------------------------------------------------------
    # Metric
    # --------------------------------------------------------

    metric = plan.get("metric", {})

    if not isinstance(metric, dict):
        metric = {}

    metric_column = str(
        metric.get("column", "")
        or ""
    ).strip()

    aggregation = str(
        metric.get("aggregation", "NONE")
        or "NONE"
    ).upper().strip()

    if aggregation not in {
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "COUNT",
        "NONE",
    }:
        aggregation = "NONE"

    result["metric"] = {
        "column": metric_column,
        "aggregation": aggregation,
    }

    # --------------------------------------------------------
    # Group By
    # --------------------------------------------------------

    group_by = plan.get("group_by", [])

    if isinstance(group_by, str):
        group_by = [group_by]

    if not isinstance(group_by, list):
        group_by = []

    result["group_by"] = [
        str(column).strip()
        for column in group_by
        if column
    ]

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    sort = plan.get("sort", {})

    if not isinstance(sort, dict):
        sort = {}

    sort_column = str(
        sort.get("column", "")
        or ""
    ).strip()

    direction = str(
        sort.get("direction", "ASC")
        or "ASC"
    ).upper().strip()

    if direction not in {
        "ASC",
        "DESC",
    }:
        direction = "ASC"

    result["sort"] = {
        "column": sort_column,
        "direction": direction,
    }

    # --------------------------------------------------------
    # Limit
    # --------------------------------------------------------

    limit = plan.get("limit")

    if limit is not None:

        try:
            limit = int(limit)

            if limit <= 0:
                limit = None

        except Exception:
            limit = None

    result["limit"] = limit

    return result


# ============================================================
# EXTRACT SEMANTIC COLUMNS
# ============================================================

def extract_semantic_columns(semantic_context):

    result = {
        "dimensions": [],
        "measures": [],
        "identifiers": [],
        "dates": [],
    }

    if not semantic_context:
        return result

    # --------------------------------------------------------
    # Dictionary format
    # --------------------------------------------------------

    if isinstance(semantic_context, dict):

        for table in semantic_context.get(
            "tables",
            [],
        ):

            if not isinstance(table, dict):
                continue

            for column in table.get(
                "columns",
                [],
            ):

                if not isinstance(column, dict):
                    continue

                name = column.get("name")

                role = str(
                    column.get("role", "")
                    or ""
                ).lower()

                if not name:
                    continue

                if role == "dimension":
                    result["dimensions"].append(name)

                elif role == "measure":
                    result["measures"].append(name)

                elif role == "identifier":
                    result["identifiers"].append(name)

                elif role == "date":
                    result["dates"].append(name)

        for key in result:
            result[key] = list(
                dict.fromkeys(result[key])
            )

        return result

    # --------------------------------------------------------
    # String schema format
    # --------------------------------------------------------

    text = str(
        semantic_context
    ).strip()

    try:

        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return extract_semantic_columns(
                parsed
            )

    except Exception:
        pass

    current_column = None

    for raw_line in text.splitlines():

        line = raw_line.strip()

        column_match = re.match(
            r'COLUMN:\s*"([^"]+)"',
            line,
            flags=re.IGNORECASE,
        )

        if column_match:

            current_column = (
                column_match.group(1)
            )

            continue

        role_match = re.match(
            r"ROLE:\s*([a-zA-Z_]+)",
            line,
            flags=re.IGNORECASE,
        )

        if (
            role_match
            and current_column
        ):

            role = (
                role_match.group(1)
                .lower()
                .strip()
            )

            if role == "dimension":
                result["dimensions"].append(
                    current_column
                )

            elif role == "measure":
                result["measures"].append(
                    current_column
                )

            elif role == "identifier":
                result["identifiers"].append(
                    current_column
                )

            elif role == "date":
                result["dates"].append(
                    current_column
                )

    for key in result:

        result[key] = list(
            dict.fromkeys(
                result[key]
            )
        )

    return result


# ============================================================
# NORMALIZE COLUMN NAME
# ============================================================

def normalize_column_name(value):

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).lower(),
    ).strip()


# ============================================================
# DIRECT COLUMN MATCH
# ============================================================

def direct_column_match(
    text,
    columns,
):

    if not columns:
        return None

    text_normalized = normalize_column_name(
        text
    )

    text_words = set(
        text_normalized.split()
    )

    candidates = []

    for column in columns:

        column_normalized = (
            normalize_column_name(column)
        )

        # Exact phrase
        if column_normalized in text_normalized:
            candidates.append(
                (
                    100 + len(column_normalized),
                    column,
                )
            )
            continue

        column_words = set(
            column_normalized.split()
        )

        overlap = len(
            text_words.intersection(
                column_words
            )
        )

        if overlap:
            candidates.append(
                (
                    overlap,
                    column,
                )
            )

    if candidates:

        candidates.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        return candidates[0][1]

    return None


# ============================================================
# CHOOSE ENTITY
# ============================================================

def choose_entity_dimension(
    question,
    dimensions,
    identifiers,
    dates,
):

    if not dimensions:
        return None

    text = str(question).strip()

    # ========================================================
    # IMPORTANT:
    #
    # First inspect the grammatical entity after "which".
    #
    # Example:
    #
    # Which department has the highest attrition?
    #
    # entity_phrase = department
    #
    # NOT:
    #
    # entire question -> Attrition
    # ========================================================

    which_match = re.search(
        r"\bwhich\s+(.+?)(?:\s+has\b|\s+have\b|\s+is\b|\s+are\b|\s+with\b|\s+shows\b|\s+show\b|\s+contains\b|\s+contain\b|\?|$)",
        text,
        flags=re.IGNORECASE,
    )

    if which_match:

        entity_phrase = (
            which_match.group(1)
            .strip()
            .rstrip("?")
            .strip()
        )

        # Try only the entity phrase.
        direct = direct_column_match(
            entity_phrase,
            dimensions,
        )

        if direct:
            return direct

        # Ask AI about only the entity phrase.
        prompt = f"""
You are the ENTITY SELECTION component of a
generic AI data analyst.

USER QUESTION:
{question}

ENTITY PHRASE:
{entity_phrase}

AVAILABLE DIMENSIONS:
{json.dumps(
    dimensions,
    indent=2,
    ensure_ascii=False,
)}

AVAILABLE IDENTIFIERS:
{json.dumps(
    identifiers,
    indent=2,
    ensure_ascii=False,
)}

Identify the dimension representing the thing
the user wants to compare.

Examples:

Which department has the highest attrition?
-> Department

Which region has the highest sales?
-> Region

Which product has the highest revenue?
-> Product Name

Which job role has the highest attrition?
-> JobRole

IMPORTANT:

- Select the entity.
- Do NOT select the metric.
- Do NOT select the filter condition.
- Use ONLY an available column.
- Never invent a column.

Return ONLY JSON:

{{
    "group_by": "EXACT COLUMN NAME"
}}
"""

        try:

            response = ask_ollama(prompt)

            parsed = clean_json(response)

            selected = parsed.get("group_by")

            if (
                selected
                and selected in dimensions
            ):
                return selected

        except Exception:
            pass

    # ========================================================
    # "BY <ENTITY>"
    # ========================================================

    by_match = re.search(
        r"\bby\s+(.+?)(?:\s+with\b|\s+having\b|\?|$)",
        text,
        flags=re.IGNORECASE,
    )

    if by_match:

        entity_phrase = (
            by_match.group(1)
            .strip()
            .rstrip("?")
            .strip()
        )

        direct = direct_column_match(
            entity_phrase,
            dimensions,
        )

        if direct:
            return direct

    # ========================================================
    # AI FALLBACK
    # ========================================================

    prompt = f"""
You are the ENTITY SELECTION component of a
generic AI data analyst.

USER QUESTION:
{question}

AVAILABLE DIMENSIONS:
{json.dumps(
    dimensions,
    indent=2,
    ensure_ascii=False,
)}

AVAILABLE IDENTIFIERS:
{json.dumps(
    identifiers,
    indent=2,
    ensure_ascii=False,
)}

Identify the entity the user wants to compare.

Examples:

Which department has the highest attrition?
-> Department

Which region has the highest sales?
-> Region

Which product has the highest sales?
-> Product Name

Which job role has the highest attrition?
-> JobRole

The entity is the thing being compared.

Do NOT choose a metric.
Do NOT choose a condition.

Use ONLY supplied columns.

Return ONLY:

{{
    "group_by": "EXACT COLUMN NAME"
}}
"""

    try:

        response = ask_ollama(prompt)

        parsed = clean_json(response)

        selected = parsed.get("group_by")

        if (
            selected
            and selected in dimensions
        ):
            return selected

    except Exception:
        pass

    return None


# ============================================================
# CHOOSE METRIC
# ============================================================

def choose_metric(
    question,
    measures,
    current_metric="",
):

    if not measures:
        return current_metric

    direct = direct_column_match(
        question,
        measures,
    )

    if direct:
        return direct

    prompt = f"""
You are the METRIC SELECTION component of a
generic AI data analyst.

USER QUESTION:
{question}

AVAILABLE MEASURES:
{json.dumps(
    measures,
    indent=2,
    ensure_ascii=False,
)}

Choose the numeric measure that should be
calculated.

Examples:

sales -> Sales-like measure
revenue -> Revenue-like measure
profit -> Profit-like measure
units sold -> Quantity-like measure
employee count -> EmployeeCount-like measure
age -> Age-like measure
income -> Income-like measure

The actual column MUST come from AVAILABLE MEASURES.

Never invent a column.

Return ONLY:

{{
    "metric": "EXACT COLUMN NAME"
}}
"""

    try:

        response = ask_ollama(prompt)

        parsed = clean_json(response)

        selected = parsed.get("metric")

        if (
            selected
            and selected in measures
        ):
            return selected

    except Exception:
        pass

    if (
        current_metric
        and current_metric in measures
    ):
        return current_metric

    return measures[0]


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):

    text = str(question).lower()

    if re.search(
        r"\btop\s+\d+\b",
        text,
    ):
        return "top"

    if re.search(
        r"\bbottom\s+\d+\b",
        text,
    ):
        return "bottom"

    if any(
        phrase in text
        for phrase in [
            "highest",
            "most",
            "maximum",
        ]
    ):
        return "highest"

    if any(
        phrase in text
        for phrase in [
            "lowest",
            "least",
            "minimum",
        ]
    ):
        return "lowest"

    return "other"


# ============================================================
# LIMIT
# ============================================================

def detect_limit(question):

    text = str(question).lower()

    top_match = re.search(
        r"\btop\s+(\d+)\b",
        text,
    )

    if top_match:

        return (
            int(top_match.group(1)),
            "DESC",
        )

    bottom_match = re.search(
        r"\bbottom\s+(\d+)\b",
        text,
    )

    if bottom_match:

        return (
            int(bottom_match.group(1)),
            "ASC",
        )

    if any(
        phrase in text
        for phrase in [
            "highest",
            "most",
            "maximum",
        ]
    ):

        return (1, "DESC")

    if any(
        phrase in text
        for phrase in [
            "lowest",
            "least",
            "minimum",
        ]
    ):

        return (1, "ASC")

    return (None, None)


# ============================================================
# CHOOSE CONDITION / FILTER
# ============================================================

def choose_condition_filter(
    question,
    dimensions,
    database_values,
):

    if not dimensions:
        return None

    values_context = (
        build_values_context(
            database_values
        )
    )

    prompt = f"""
You are the CONDITION DETECTION component of a
generic AI data analyst.

USER QUESTION:

{question}

AVAILABLE DIMENSIONS:

{json.dumps(
    dimensions,
    indent=2,
    ensure_ascii=False,
)}

AVAILABLE DATA VALUES:

{values_context}

Determine whether the question contains a
condition/filter.

IMPORTANT DISTINCTION:

ENTITY = what is being compared.

CONDITION = which records are included.

METRIC = what is measured.

Example:

Which department has the highest employee attrition?

ENTITY:
Department

CONDITION:
Attrition = Yes

METRIC:
EmployeeCount

Therefore the filter is:

Attrition = Yes

Another example:

Which region has the highest sales for Electronics?

ENTITY:
Region

CONDITION:
Category = Electronics

Another example:

Which products have the highest sales in the West?

ENTITY:
Product

CONDITION:
Region = West

Rules:

1. Use ONLY actual dimensions.
2. Use ONLY actual data values.
3. Do not invent values.
4. If there is no condition, return null.
5. Do NOT use the entity as the filter.
6. Words such as highest, lowest, top, bottom are
   ranking instructions, NOT filters.

Return ONLY:

{{
    "filter": null
}}

OR:

{{
    "filter": {{
        "column": "EXACT DIMENSION",
        "operator": "=",
        "value": "EXACT DATA VALUE"
    }}
}}
"""

    try:

        response = ask_ollama(prompt)

        parsed = clean_json(response)

        condition = parsed.get("filter")

        if not condition:
            return None

        if not isinstance(condition, dict):
            return None

        column = condition.get("column")

        operator = condition.get(
            "operator",
            "=",
        )

        value = condition.get("value")

        if column not in dimensions:
            return None

        if operator not in {
            "=",
            "!=",
            ">",
            "<",
            ">=",
            "<=",
            "LIKE",
        }:
            operator = "="

        if value is None:
            return None

        return {
            "column": column,
            "operator": operator,
            "value": value,
        }

    except Exception:
        return None


# ============================================================
# AGGREGATION REPAIR
# ============================================================

def repair_aggregation(
    plan,
    question,
):

    text = str(question).lower()

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "how many",
            "number of",
            "count of",
        ]
    ):

        plan["intent"] = "count"

        plan["metric"] = {
            "column": "*",
            "aggregation": "COUNT",
        }

        return plan

    # --------------------------------------------------------
    # AVERAGE
    # --------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "average",
            "avg",
            "mean",
        ]
    ):

        if plan["intent"] != "ranking":
            plan["intent"] = "aggregate"

        plan["metric"]["aggregation"] = "AVG"

        return plan

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "total",
            "sum of",
            "combined",
        ]
    ):

        if plan["intent"] != "ranking":
            plan["intent"] = "aggregate"

        plan["metric"]["aggregation"] = "SUM"

        return plan

    # --------------------------------------------------------
    # MAX
    # --------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "maximum",
            "max",
        ]
    ):

        if plan["intent"] != "ranking":
            plan["intent"] = "aggregate"

        plan["metric"]["aggregation"] = "MAX"

        return plan

    # --------------------------------------------------------
    # MIN
    # --------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "minimum",
            "min",
        ]
    ):

        if plan["intent"] != "ranking":
            plan["intent"] = "aggregate"

        plan["metric"]["aggregation"] = "MIN"

        return plan

    return plan


# ============================================================
# RANKING REPAIR
# ============================================================

def repair_ranking_plan(
    plan,
    question,
    semantic_context,
    database_values,
):

    semantics = extract_semantic_columns(
        semantic_context
    )

    dimensions = semantics["dimensions"]
    measures = semantics["measures"]
    identifiers = semantics["identifiers"]
    dates = semantics["dates"]

    question_type = detect_question_type(
        question
    )

    limit, direction = detect_limit(
        question
    )

    # ========================================================
    # RANKING
    # ========================================================

    if limit is not None:

        plan["intent"] = "ranking"

        plan["limit"] = limit

        plan["sort"]["direction"] = direction

    # ========================================================
    # ENTITY
    # ========================================================

    selected_entity = None

    if (
        plan["intent"] == "ranking"
        or question_type != "other"
    ):

        selected_entity = choose_entity_dimension(
            question,
            dimensions,
            identifiers,
            dates,
        )

    if selected_entity:

        plan["group_by"] = [
            selected_entity
        ]

    else:

        # Keep an already valid group.
        existing_group = None

        for column in plan.get(
            "group_by",
            [],
        ):

            if column in dimensions:

                existing_group = column
                break

        if existing_group:

            plan["group_by"] = [
                existing_group
            ]

    # ========================================================
    # CONDITION
    # ========================================================

    condition = choose_condition_filter(
        question,
        dimensions,
        database_values,
    )

    # Never allow the entity to become its own filter.
    if (
        condition
        and plan.get("group_by")
        and condition["column"]
        == plan["group_by"][0]
    ):

        condition = None

    if condition:

        already_exists = False

        for existing in plan.get(
            "filters",
            [],
        ):

            if (
                existing.get("column")
                == condition["column"]
                and str(
                    existing.get("value")
                ).lower()
                == str(
                    condition["value"]
                ).lower()
            ):

                already_exists = True
                break

        if not already_exists:

            plan["filters"].append(
                condition
            )

    # ========================================================
    # METRIC
    # ========================================================

    if measures:

        metric = choose_metric(
            question,
            measures,
            plan["metric"].get(
                "column",
                "",
            ),
        )

        if metric:

            aggregation = plan[
                "metric"
            ].get(
                "aggregation",
                "NONE",
            )

            if (
                plan["intent"] == "ranking"
                and aggregation
                in {
                    "",
                    None,
                    "NONE",
                }
            ):

                aggregation = "SUM"

            if aggregation not in {
                "SUM",
                "AVG",
                "MIN",
                "MAX",
                "COUNT",
            }:

                aggregation = "SUM"

            plan["metric"] = {
                "column": metric,
                "aggregation": aggregation,
            }

    # ========================================================
    # SORT
    # ========================================================

    if (
        plan["intent"] == "ranking"
        and plan["metric"].get("column")
    ):

        plan["sort"]["column"] = (
            plan["metric"]["column"]
        )

        if direction:
            plan["sort"]["direction"] = direction

        elif plan["sort"].get(
            "direction"
        ) not in {
            "ASC",
            "DESC",
        }:

            plan["sort"]["direction"] = "DESC"

    return plan


# ============================================================
# VALIDATE PLAN
# ============================================================

def validate_plan(
    plan,
    semantic_context,
):

    semantics = extract_semantic_columns(
        semantic_context
    )

    dimensions = set(
        semantics["dimensions"]
    )

    measures = set(
        semantics["measures"]
    )

    identifiers = set(
        semantics["identifiers"]
    )

    # --------------------------------------------------------
    # GROUP BY
    # --------------------------------------------------------

    valid_groups = []

    for column in plan.get(
        "group_by",
        [],
    ):

        if (
            column in dimensions
            or column in identifiers
        ):

            valid_groups.append(column)

    plan["group_by"] = list(
        dict.fromkeys(
            valid_groups
        )
    )

    # --------------------------------------------------------
    # METRIC
    # --------------------------------------------------------

    metric = plan[
        "metric"
    ].get("column")

    if (
        metric
        and metric != "*"
        and metric not in measures
    ):

        plan["metric"] = {
            "column": "",
            "aggregation": "NONE",
        }

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    valid_filters = []

    for condition in plan.get(
        "filters",
        [],
    ):

        column = condition.get(
            "column"
        )

        if (
            column in dimensions
            or column in identifiers
        ):

            valid_filters.append(
                condition
            )

    plan["filters"] = valid_filters

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    if (
        plan["intent"] == "ranking"
        and plan["metric"].get("column")
    ):

        plan["sort"]["column"] = (
            plan["metric"]["column"]
        )

        if plan["sort"].get(
            "direction"
        ) not in {
            "ASC",
            "DESC",
        }:

            plan["sort"]["direction"] = "DESC"

    return plan


# ============================================================
# MAIN PLANNER
# ============================================================

def create_query_plan(
    question,
    schema,
    database_values,
    semantic_context=None,
):

    tables = extract_tables(schema)

    if not tables:

        raise ValueError(
            "No tables found in the active dataset."
        )

    values_context = build_values_context(
        database_values
    )

    semantic_text = build_semantic_context(
        semantic_context
    )

    # ========================================================
    # INITIAL LLM PLAN
    # ========================================================

    prompt = f"""
You are the Query Planning Agent for QuantIQ.

QuantIQ is a generic AI Data Analyst.

The user can upload ANY dataset.

Your job is to understand a natural-language
question and create a structured query plan.

DO NOT generate SQL.

============================================================
TABLES
============================================================

{json.dumps(
    tables,
    indent=2,
    ensure_ascii=False,
)}

============================================================
SCHEMA
============================================================

{schema}

============================================================
SEMANTIC ANALYSIS
============================================================

{semantic_text}

============================================================
ACTUAL DATA VALUES
============================================================

{values_context}

============================================================
USER QUESTION
============================================================

{question}

============================================================
REASONING
============================================================

Separate:

ENTITY:
What is being compared?

CONDITION:
Which records should be included?

METRIC:
What numeric value should be measured?

AGGREGATION:
How should that metric be calculated?

RANKING:
How should results be sorted?

LIMIT:
How many results are requested?

============================================================
EXAMPLE
============================================================

Question:

Which department has the highest employee attrition?

ENTITY:
Department

CONDITION:
Attrition = Yes

METRIC:
EmployeeCount

AGGREGATION:
SUM

RANKING:
DESC

LIMIT:
1

The correct conceptual plan is:

group_by = Department
filter = Attrition = Yes
metric = EmployeeCount
aggregation = SUM
sort = EmployeeCount DESC
limit = 1

Do NOT put Attrition in group_by.

============================================================
ANOTHER EXAMPLE
============================================================

Which region has the highest sales for Electronics?

ENTITY:
Region

CONDITION:
Category = Electronics

METRIC:
Sales

AGGREGATION:
SUM

============================================================
RULES
============================================================

- Use ONLY supplied tables.
- Use ONLY supplied columns.
- Use ONLY supplied values.
- Never invent columns.
- Never invent values.
- The entity being compared belongs in group_by.
- Conditions belong in filters.
- Numeric measures belong in metric.
- "top N" means DESC with N.
- "highest" means DESC with 1.
- "lowest" means ASC with 1.
- "bottom N" means ASC with N.

Return ONLY valid JSON.

NO markdown.
NO SQL.
NO explanation.

============================================================
JSON
============================================================

{{
    "intent": "select | count | aggregate | ranking",
    "table": "ACTUAL TABLE",
    "filters": [],
    "metric": {{
        "column": "ACTUAL MEASURE",
        "aggregation": "SUM | AVG | MIN | MAX | COUNT | NONE"
    }},
    "group_by": [],
    "sort": {{
        "column": "ACTUAL COLUMN",
        "direction": "ASC | DESC"
    }},
    "limit": null
}}
"""

    response = ask_ollama(prompt)

    plan = clean_json(response)

    plan = normalize_plan(plan)

    # ========================================================
    # GENERIC REPAIR
    # ========================================================

    plan = repair_aggregation(
        plan,
        question,
    )

    plan = repair_ranking_plan(
        plan,
        question,
        semantic_context,
        database_values,
    )

    plan = validate_plan(
        plan,
        semantic_context,
    )

    return plan


# ============================================================
# COMPATIBILITY
# ============================================================

generate_query_plan = create_query_plan