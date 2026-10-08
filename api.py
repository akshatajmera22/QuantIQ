import os
import sqlite3
import math
from datetime import date, datetime

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from planner import create_query_plan
from sql_builder import build_sql
from data_manager import (
    get_active_dataset,
    get_active_database_path,
    list_datasets,
    set_active_dataset,
    create_uploaded_dataset,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


app = FastAPI(
    title="Quantiq API",
    description="AI Data Analyst Backend",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class QueryRequest(BaseModel):
    question: str


class DatasetSelectRequest(BaseModel):
    dataset_id: str


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection(database_path=None):
    return sqlite3.connect(
        database_path or get_active_database_path()
    )


# ============================================================
# GET TABLES
# ============================================================

def get_tables(database_path=None):
    conn = get_connection(database_path)

    try:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        return [row[0] for row in rows]

    finally:
        conn.close()


# ============================================================
# GET DATABASE SCHEMA
# ============================================================

def get_schema(database_path=None):
    database_path = (
        database_path
        or get_active_database_path()
    )

    conn = get_connection(database_path)

    try:
        schema_parts = []

        for table in get_tables(database_path):

            safe_table = table.replace('"', '""')

            columns = conn.execute(
                f'PRAGMA table_info("{safe_table}")'
            ).fetchall()

            schema_parts.append(
                f'TABLE: "{table}"'
            )

            for column in columns:
                schema_parts.append(
                    f'- "{column[1]}" ({column[2]})'
                )

            schema_parts.append("")

        return "\n".join(schema_parts)

    finally:
        conn.close()


# ============================================================
# GET REAL DATABASE VALUES
# ============================================================

def get_database_values(database_path=None):
    database_path = (
        database_path
        or get_active_database_path()
    )

    conn = get_connection(database_path)

    try:
        database_values = {}

        for table in get_tables(database_path):

            safe_table = table.replace('"', '""')

            columns = conn.execute(
                f'PRAGMA table_info("{safe_table}")'
            ).fetchall()

            database_values[table] = {}

            for column in columns:

                column_name = column[1]
                column_type = str(column[2]).upper()

                if column_type not in (
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
                        f"""
                        SELECT DISTINCT "{safe_column}"
                        FROM "{safe_table}"
                        WHERE "{safe_column}" IS NOT NULL
                        LIMIT 500
                        """
                    ).fetchall()

                except Exception:
                    continue

                values = [
                    str(row[0]).strip()
                    for row in rows
                    if (
                        row[0] is not None
                        and str(row[0]).strip()
                    )
                ]

                database_values[table][
                    column_name
                ] = values

        return database_values

    finally:
        conn.close()


# ============================================================
# EXECUTE SQL
# ============================================================

def execute_sql(sql, database_path=None):

    conn = get_connection(database_path)

    try:

        return pd.read_sql_query(
            sql,
            conn
        )

    finally:
        conn.close()


# ============================================================
# MAKE VALUES JSON SAFE
# ============================================================

def make_json_safe(value):

    if value is None:
        return None

    try:

        missing = pd.isna(value)

        if isinstance(missing, bool) and missing:
            return None

    except Exception:
        pass

    if isinstance(value, float):

        if math.isnan(value) or math.isinf(value):
            return None

        return value

    if isinstance(
        value,
        (int, str, bool)
    ):
        return value

    if isinstance(
        value,
        (datetime, date)
    ):
        return value.isoformat()

    if hasattr(value, "item"):

        try:
            return make_json_safe(
                value.item()
            )

        except Exception:
            pass

    if isinstance(value, list):

        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, dict):

        return {
            str(key): make_json_safe(val)
            for key, val in value.items()
        }

    return str(value)


# ============================================================
# DATAFRAME → JSON
# ============================================================

def dataframe_to_json(result):

    rows = []

    for _, row in result.iterrows():

        rows.append(
            {
                str(column): make_json_safe(
                    row[column]
                )
                for column in result.columns
            }
        )

    return rows


# ============================================================
# GENERATE HUMAN ANSWER
# ============================================================

def generate_answer(question, result):

    # --------------------------------------------------------
    # NO RESULT
    # --------------------------------------------------------

    if result is None:

        return (
            "I couldn't retrieve a result."
        )

    if result.empty:

        return (
            "I couldn't find any records "
            "matching your request."
        )

    # --------------------------------------------------------
    # SINGLE VALUE
    # Example:
    # What is the average selling price?
    # --------------------------------------------------------

    if (
        len(result) == 1
        and len(result.columns) == 1
    ):

        value = result.iloc[0, 0]

        column = str(
            result.columns[0]
        )

        if pd.notna(value):

            if isinstance(value, float):

                return (
                    f"The {column} is "
                    f"{value:,.2f}."
                )

            if isinstance(value, int):

                return (
                    f"The {column} is "
                    f"{value:,}."
                )

            return (
                f"The result is {value}."
            )

    # --------------------------------------------------------
    # ONE RECORD
    # --------------------------------------------------------

    if len(result) == 1:

        return (
            "Here is the matching record."
        )

    # --------------------------------------------------------
    # MULTIPLE RECORDS
    # --------------------------------------------------------

    return (
        f"Here are the "
        f"{len(result):,} matching records."
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "application": "Quantiq",
        "message": "Quantiq API is running.",
    }


# ============================================================
# DATASETS
# ============================================================

@app.get("/datasets")
def datasets():

    active = get_active_dataset()

    return {
        "success": True,
        "active": active,
        "datasets": list_datasets(),
    }


# ============================================================
# SELECT DATASET
# ============================================================

@app.post("/datasets/select")
def select_dataset(
    request: DatasetSelectRequest
):

    try:

        active = set_active_dataset(
            request.dataset_id
        )

        return {
            "success": True,
            "active": active,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# ============================================================
# UPLOAD DATA
# ============================================================

@app.post("/upload")
async def upload_data(
    source_type: str = Form(...),
    files: list[UploadFile] = File(...),
):

    source_type = (
        source_type
        .lower()
        .strip()
    )

    if source_type not in {
        "excel",
        "csv"
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "This upload endpoint currently "
                "supports Excel and CSV. "
                "MySQL and SQL Server will "
                "be added after file uploads "
                "are working."
            ),
        )

    if not files:

        raise HTTPException(
            status_code=400,
            detail="No files were uploaded.",
        )

    try:

        dataset = create_uploaded_dataset(
            files,
            source_type,
        )

        return {
            "success": True,
            "message": (
                "Dataset uploaded and activated."
            ),
            "active": dataset,
            "datasets": list_datasets(),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# ============================================================
# DATABASE INFORMATION
# ============================================================

@app.get("/database")
def database_info():

    active = get_active_dataset()

    database_path = (
        get_active_database_path()
    )

    return {
        "success": True,
        "database": database_path,
        "active_dataset": active,
        "tables": get_tables(database_path),
        "schema": get_schema(database_path),
    }


# ============================================================
# MAIN QUERY ENDPOINT
# ============================================================

@app.post("/query")
def query_database(
    request: QueryRequest
):

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:

        # ----------------------------------------------------
        # ACTIVE DATASET
        # ----------------------------------------------------

        active = get_active_dataset()

        database_path = (
            get_active_database_path()
        )

        # ----------------------------------------------------
        # REAL SCHEMA
        # ----------------------------------------------------

        schema = get_schema(
            database_path
        )

        # ----------------------------------------------------
        # REAL DATABASE VALUES
        # ----------------------------------------------------

        database_values = (
            get_database_values(
                database_path
            )
        )

        # ----------------------------------------------------
        # AI QUERY PLAN
        # ----------------------------------------------------

        query_plan = create_query_plan(
            question,
            schema,
            database_values,
        )

        # ----------------------------------------------------
        # BUILD SQL
        # ----------------------------------------------------

        sql = build_sql(
            query_plan,
            database_path,
        )

        # ----------------------------------------------------
        # EXECUTE SQL
        # ----------------------------------------------------

        result = execute_sql(
            sql,
            database_path,
        )

        # ----------------------------------------------------
        # GENERATE HUMAN ANSWER
        # ----------------------------------------------------

        answer = generate_answer(
            question,
            result,
        )

        # ----------------------------------------------------
        # CONVERT RESULT TO JSON
        # ----------------------------------------------------

        rows = dataframe_to_json(
            result
        )

        # ----------------------------------------------------
        # RETURN EVERYTHING
        # ----------------------------------------------------

        return {
            "success": True,

            "question": question,

            "answer": answer,

            "sql": sql,

            "query_plan": query_plan,

            "row_count": len(result),

            "rows": rows,

            "dataset": active,
        }

    except Exception as exc:

        return {
            "success": False,
            "question": question,
            "error": str(exc),
        }