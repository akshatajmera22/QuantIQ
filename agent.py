import os
import re
import sqlite3
import subprocess
import json
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

MODEL_NAME = "llama3.1:8b"

# Your GTX 1650 has 4GB VRAM.
# We intentionally run Ollama CPU-side from this backend
# to avoid llama-server CUDA crashes.
OLLAMA_NUM_GPU = "0"

# Keep context reasonably small.
OLLAMA_CONTEXT = "2048"

MAX_VALUES_PER_COLUMN = 500


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def get_tables():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        return [row[0] for row in rows]

    finally:
        conn.close()


def get_schema():
    conn = get_connection()

    try:
        parts = []

        for table in get_tables():

            safe_table = table.replace('"', '""')

            columns = conn.execute(
                f'PRAGMA table_info("{safe_table}")'
            ).fetchall()

            parts.append(f'TABLE: "{table}"')

            for column in columns:

                parts.append(
                    f'- "{column[1]}" ({column[2]})'
                )

            parts.append("")

        return "\n".join(parts)

    finally:
        conn.close()


# ============================================================
# DATABASE VALUES
# ============================================================

def get_database_values():

    conn = get_connection()

    try:

        database_values = {}

        for table in get_tables():

            safe_table = table.replace(
                '"',
                '""'
            )

            columns = conn.execute(
                f'PRAGMA table_info("{safe_table}")'
            ).fetchall()

            database_values[table] = {}

            for column in columns:

                column_name = column[1]
                data_type = str(
                    column[2]
                ).upper()

                if data_type not in (
                    "TEXT",
                    "VARCHAR",
                    "CHAR"
                ):
                    continue

                safe_column = column_name.replace(
                    '"',
                    '""'
                )

                try:

                    rows = conn.execute(
                        f'''
                        SELECT DISTINCT "{safe_column}"
                        FROM "{safe_table}"
                        WHERE "{safe_column}" IS NOT NULL
                        LIMIT {MAX_VALUES_PER_COLUMN}
                        '''
                    ).fetchall()

                except Exception:
                    continue

                values = []

                for row in rows:

                    if row[0] is None:
                        continue

                    value = str(
                        row[0]
                    ).strip()

                    if value:
                        values.append(value)

                database_values[
                    table
                ][
                    column_name
                ] = values

        return database_values

    finally:
        conn.close()


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value):

    value = str(value).lower().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def compact_text(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize_text(value)
    )


# ============================================================
# EXACT VALUE MATCHING
# ============================================================

def value_is_in_question(
    value,
    question
):

    value_normalized = normalize_text(
        value
    )

    question_normalized = normalize_text(
        question
    )

    value_words = value_normalized.split()
    question_words = question_normalized.split()

    if not value_words:
        return False

    # Single-word values
    if len(value_words) == 1:

        return value_words[0] in question_words

    # Multi-word values
    n = len(value_words)

    for i in range(
        len(question_words) - n + 1
    ):

        if (
            question_words[i:i + n]
            == value_words
        ):

            return True

    return False


# ============================================================
# DETERMINISTIC DATABASE VALUE MATCHING
# ============================================================

def deterministic_value_matching(question):

    database_values = get_database_values()

    matches = []

    for table, columns in database_values.items():

        for column, values in columns.items():

            for value in values:

                if value_is_in_question(
                    value,
                    question
                ):

                    matches.append(
                        {
                            "table": table,
                            "column": column,
                            "value": value
                        }
                    )

    # Remove duplicates

    unique = []
    seen = set()

    for match in matches:

        key = (
            match["table"],
            match["column"],
            match["value"].lower()
        )

        if key not in seen:

            seen.add(key)

            unique.append(match)

    return unique


# ============================================================
# OLLAMA
# ============================================================

def ask_ollama(prompt):

    """
    Call Ollama through the CLI instead of the Python
    ollama.chat() client.

    This is intentional because the CLI has already been
    confirmed to work on this machine.

    We also force CPU execution to avoid the GTX 1650
    CUDA / llama-server crash.
    """

    env = os.environ.copy()

    env["OLLAMA_NUM_GPU"] = OLLAMA_NUM_GPU

    command = [
        "ollama",
        "run",
        MODEL_NAME,
        prompt
    ]

    try:

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env=env
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "Ollama timed out while generating a response."
        )

    except FileNotFoundError:

        raise RuntimeError(
            "Ollama was not found. "
            "Make sure Ollama is installed and available "
            "from PowerShell."
        )

    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    if process.returncode != 0:

        raise RuntimeError(
            "Ollama failed.\n\n"
            + (
                stderr
                if stderr
                else stdout
            )
        )

    if not stdout:

        raise RuntimeError(
            "Ollama returned an empty response."
        )

    return stdout.strip()


# ============================================================
# CLEAN SQL
# ============================================================

def clean_sql(text):

    if not text:
        return None

    text = text.strip()

    text = re.sub(
        r"```sql",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```sqlite",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.replace(
        "```",
        ""
    )

    match = re.search(
        r"\bSELECT\b.*",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    sql = match.group(0).strip()

    if ";" in sql:

        sql = (
            sql.split(
                ";",
                1
            )[0]
            + ";"
        )

    return sql.strip()


# ============================================================
# SQL VALIDATION
# ============================================================

def validate_sql(sql):

    if not sql:

        return (
            False,
            "No SQL was generated."
        )

    normalized = sql.lower().strip()

    if not normalized.startswith("select"):

        return (
            False,
            "Only SELECT queries are allowed."
        )

    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "replace ",
        "truncate ",
        "attach ",
        "detach ",
        "pragma "
    ]

    for command in forbidden:

        if command in normalized:

            return (
                False,
                f"Unsafe SQL operation: "
                f"{command.strip()}"
            )

    return True, ""


# ============================================================
# GENERATE SQL
# ============================================================

def generate_sql(
    question,
    schema,
    matched_values
):

    matched_text = ""

    if matched_values:

        matched_text = (
            "\n\nVALUES EXPLICITLY "
            "IDENTIFIED FROM THE USER'S QUESTION:\n"
        )

        for item in matched_values:

            matched_text += (
                f'- Table: "{item["table"]}" | '
                f'Column: "{item["column"]}" | '
                f'Exact value: "{item["value"]}"\n'
            )

    prompt = f"""
You are an expert SQLite data analyst.

DATABASE SCHEMA:

{schema}

USER QUESTION:

{question}

{matched_text}

Generate ONE correct SQLite SELECT query.

============================================================
RULES
============================================================

1. Use ONLY tables and columns in the schema.

2. Never invent tables.

3. Never invent columns.

4. Preserve every condition explicitly requested
   by the user.

5. Every value explicitly identified above MUST
   appear in the SQL.

6. Use the exact database value supplied.

7. For text comparisons use:

LOWER("column") = LOWER('value')

8. NEVER add a filter that the user did not request.

9. NEVER infer extra filters from database relationships.

10. If the user says:

    electric green Audi Q7

    use:

    Make = Audi
    Model = Q7
    Fuel_Type = Electric
    Color = Green

    Do NOT add:

    Body_Type = SUV

11. If the user says "electric",
    filter Fuel_Type.

12. If the user says "green",
    filter Color.

13. If the user says "silver",
    filter Color.

14. If the user says "in IL",
    filter Location.

15. If the user says "Mercedes Benz",
    use the actual database value
    Mercedes-Benz.

16. For "how many", use COUNT(*).

17. For "total", use SUM().

18. For "average", use AVG().

19. For "highest", use:

    ORDER BY column DESC
    LIMIT 1

20. For "lowest", use:

    ORDER BY column ASC
    LIMIT 1

21. For "top N", use:

    ORDER BY column DESC
    LIMIT N

22. For "most expensive", use:

    ORDER BY "Selling_Price" DESC

23. For "highest horsepower", use:

    ORDER BY "Horsepower" DESC

24. For "find", "show", or "list",
    return matching records.

25. Do not use SELECT * for calculation questions.

26. Quote table and column names using
    double quotes.

27. Return ONLY SQL.

28. Do not explain.

============================================================
EXAMPLES
============================================================

Question:

top 5 most expensive cars

Correct:

SELECT *
FROM "automobile_dataset"
ORDER BY "Selling_Price" DESC
LIMIT 5;

============================================================

Question:

which car has the highest horsepower?

Correct:

SELECT *
FROM "automobile_dataset"
ORDER BY "Horsepower" DESC
LIMIT 1;

============================================================

Question:

electric green Audi Q7

Correct:

SELECT *
FROM "automobile_dataset"
WHERE LOWER("Make") = LOWER('Audi')
AND LOWER("Model") = LOWER('Q7')
AND LOWER("Fuel_Type") = LOWER('Electric')
AND LOWER("Color") = LOWER('Green');

============================================================

Question:

how many silver Mercedes-Benz in IL

Correct:

SELECT COUNT(*)
FROM "automobile_dataset"
WHERE LOWER("Make") = LOWER('Mercedes-Benz')
AND LOWER("Color") = LOWER('Silver')
AND LOWER("Location") = LOWER('IL');

============================================================

NOW GENERATE SQL FOR:

{question}
"""

    response = ask_ollama(prompt)

    sql = clean_sql(response)

    valid, error = validate_sql(sql)

    if not valid:

        raise ValueError(
            f"{error}\n\n"
            f"Generated SQL:\n{sql}"
        )

    return sql


# ============================================================
# VERIFY REQUIRED VALUES
# ============================================================

def verify_sql_contains_values(
    sql,
    matched_values
):

    if not matched_values:

        return True, ""

    sql_normalized = normalize_text(sql)

    sql_compact = compact_text(sql)

    missing = []

    for item in matched_values:

        column = normalize_text(
            item["column"]
        )

        value = normalize_text(
            item["value"]
        )

        value_compact = compact_text(
            item["value"]
        )

        if column not in sql_normalized:

            missing.append(
                f'{item["column"]} = '
                f'{item["value"]}'
            )

            continue

        if value not in sql_normalized:

            if value_compact not in sql_compact:

                missing.append(
                    f'{item["column"]} = '
                    f'{item["value"]}'
                )

    if missing:

        return (
            False,
            "Generated SQL omitted required "
            "database values: "
            + ", ".join(missing)
        )

    return True, ""


# ============================================================
# EXECUTE SQL
# ============================================================

def execute_sql(sql):

    conn = get_connection()

    try:

        result = pd.read_sql_query(
            sql,
            conn
        )

        return result, None

    except Exception as e:

        return None, str(e)

    finally:

        conn.close()


# ============================================================
# DISPLAY RESULT
# ============================================================

def display_result(result):

    if result is None:

        print("No result.")

        return

    if result.empty:

        print(
            "No matching records."
        )

        return

    print(
        f"Rows returned: {len(result)}"
    )

    print()

    if len(result) > 20:

        print(
            result.head(20).to_string(
                index=False
            )
        )

        print()

        print(
            f"... {len(result) - 20} "
            "additional rows hidden."
        )

    else:

        print(
            result.to_string(
                index=False
            )
        )


# ============================================================
# NATURAL LANGUAGE ANSWER
# ============================================================

def generate_answer(
    question,
    result
):

    if result is None:

        return (
            "I couldn't retrieve a result "
            "from the database."
        )

    if result.empty:

        return (
            "I couldn't find any records "
            "matching your request."
        )

    # Keep prompt size under control.
    if len(result) > 20:

        result_text = (
            result.head(20)
            .to_string(
                index=False
            )
        )

        result_text += (
            f"\n... {len(result) - 20} "
            "additional records."
        )

    else:

        result_text = (
            result.to_string(
                index=False
            )
        )

    prompt = f"""
You are the final answer generator for an AI Data Analyst.

USER QUESTION:

{question}

DATABASE RESULT:

{result_text}

Answer the user's question directly.

RULES:

1. The database result is the only source of truth.

2. Never invent information.

3. Never invent numbers.

4. Never invent records.

5. Never add conditions.

6. Answer the actual question.

7. Do not answer with one random column.

8. If the user asks to find/show/list something,
   summarize the matching records.

9. If exactly one record matches, identify the
   relevant record clearly.

10. If multiple records match, state how many.

11. For rankings, clearly identify the requested
    top/highest/lowest records.

12. For numerical questions, explain the number naturally.

13. Do not mention SQL.

14. Do not mention SQLite.

15. Do not describe the database.

16. Use proper English.

17. Keep the answer concise.

18. If the question asks for TOP N, provide exactly
    N records when N records are present.

19. Never reduce a TOP N answer just because two records
    have the same value. They are still separate records.

20. If records are tied, show every requested record.

============================================================

Example:

Question:
top 5 cars with most horsepower

If the result contains 5 rows, answer with all 5 rows.

Question:
which car has the highest horsepower?

If the result contains one row, identify that car
and its horsepower.

Question:
how many silver Mercedes-Benz?

If the result is:

COUNT(*)
53

Answer:

There are 53 silver Mercedes-Benz vehicles.

Question:
electric green Audi Q7

If one record is returned:

I found 1 electric green Audi Q7.

Return ONLY the final answer.

USER QUESTION:

{question}

DATABASE RESULT:

{result_text}
"""

    try:

        answer = ask_ollama(prompt)

        if answer:

            return answer.strip()

    except Exception as e:

        print()
        print(
            "Ollama answer generation failed:"
        )
        print(e)

    # ========================================================
    # FALLBACK
    # ========================================================

    if len(result) == 1:

        row = result.iloc[0]

        if (
            "Make" in result.columns
            and "Model" in result.columns
        ):

            make = row.get("Make")
            model = row.get("Model")

            horsepower = row.get("Horsepower")

            if (
                "horsepower"
                in question.lower()
                and pd.notna(horsepower)
            ):

                return (
                    f"The car with the highest "
                    f"horsepower is the "
                    f"{make} {model}, with "
                    f"{horsepower:g} horsepower."
                )

            fuel = row.get("Fuel_Type")
            color = row.get("Color")

            description = ""

            if pd.notna(fuel):

                description += (
                    str(fuel) + " "
                )

            if pd.notna(color):

                description += (
                    str(color) + " "
                )

            description += (
                f"{make} {model}"
            )

            return (
                f"I found 1 "
                f"{description}."
            )

        return (
            "I found 1 matching record."
        )

    # COUNT result
    if (
        len(result.columns) == 1
        and len(result) == 1
    ):

        value = result.iloc[0, 0]

        if pd.notna(value):

            return (
                f"The result is "
                f"{value:,}."
            )

    return (
        f"I found {len(result):,} "
        "matching records."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 60)

    print(
        "AI DATA ANALYST"
    )

    print("=" * 60)

    print()

    print("Database:")

    print(DATABASE_PATH)

    if not os.path.exists(
        DATABASE_PATH
    ):

        print()

        print(
            "ERROR: database.db "
            "was not found."
        )

        return

    print()

    print("Tables:")

    for table in get_tables():

        print(
            f"- {table}"
        )

    print()

    print("Database schema:")

    print()

    print(
        get_schema()
    )

    while True:

        print()

        question = input(
            "Ask your database a question: "
        ).strip()

        if not question:

            continue

        if question.lower() in {
            "exit",
            "quit",
            "q"
        }:

            print(
                "Goodbye."
            )

            break

        # ====================================================
        # VALUE MATCHING
        # ====================================================

        print()

        print(
            "Finding values in the dataset..."
        )

        try:

            matched_values = (
                deterministic_value_matching(
                    question
                )
            )

        except Exception as e:

            print()

            print(
                "VALUE MATCHING ERROR:"
            )

            print(e)

            continue

        if matched_values:

            print()

            print(
                "MATCHED DATABASE VALUES:"
            )

            for item in matched_values:

                print(
                    f'- {item["column"]}: '
                    f'{item["value"]}'
                )

        else:

            print()

            print(
                "No specific database values "
                "identified."
            )

        # ====================================================
        # SQL GENERATION
        # ====================================================

        print()

        print(
            "Generating SQL..."
        )

        try:

            schema = get_schema()

            sql = generate_sql(
                question,
                schema,
                matched_values
            )

        except Exception as e:

            print()

            print(
                "SQL GENERATION ERROR:"
            )

            print(e)

            continue

        print()

        print(
            "GENERATED SQL:"
        )

        print(sql)

        # ====================================================
        # SQL VALIDATION
        # ====================================================

        valid, error = (
            validate_sql(
                sql
            )
        )

        if not valid:

            print()

            print(
                "SQL REJECTED:"
            )

            print(error)

            continue

        # ====================================================
        # REQUIRED VALUE VALIDATION
        # ====================================================

        valid, error = (
            verify_sql_contains_values(
                sql,
                matched_values
            )
        )

        if not valid:

            print()

            print(
                "SQL REJECTED:"
            )

            print(error)

            continue

        # ====================================================
        # EXECUTE
        # ====================================================

        print()

        print(
            "Executing SQL..."
        )

        result, error = (
            execute_sql(
                sql
            )
        )

        if error:

            print()

            print(
                "SQL ERROR:"
            )

            print(error)

            continue

        # ====================================================
        # DATABASE RESULT
        # ====================================================

        print()

        print(
            "DATABASE RESULT:"
        )

        display_result(
            result
        )

        # ====================================================
        # FINAL ANSWER
        # ====================================================

        print()

        print(
            "Generating answer..."
        )

        answer = generate_answer(
            question,
            result
        )

        print()

        print(
            "ANSWER:"
        )

        print(
            answer
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()