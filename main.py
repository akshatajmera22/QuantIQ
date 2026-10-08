import os
import re
import traceback

from typing import (
    Any,
    Dict,
    Optional,
    List,
)

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from pydantic import (
    BaseModel,
    Field,
)

from dotenv import load_dotenv


# ============================================================
# OPTIONAL DEPENDENCIES
# ============================================================

try:
    import duckdb
except ImportError:
    duckdb = None


try:
    import pandas as pd
except ImportError:
    pd = None


# ============================================================
# QUANTIQ MODULES
# ============================================================

from mysql_engine import (
    create_connection,
    test_connection,
    list_databases,
    list_tables,
    get_schema,
    get_database_values,
    execute_query,
    validate_read_only_sql,
    build_schema_context,
    clean_mysql_error,
)

from gemini_planner import (
    create_plan,
)

from sql_generator import (
    generate_sql,
)

from answer_agent import (
    generate_answer,
)

from context_selector import (
    select_context,
)

from conversation_context import (
    build_conversation_context,
)

from security.schema_filter import (
    filter_schema_text,
)

from security.sql_security import (
    validate_generated_queries,
)

from security.security_config import (
    get_security_summary,
    is_table_blocked,
    is_column_blocked,
)

from security.ai_result_filter import (
    filter_results_for_ai,
)

from security.ai_data_policy import (
    get_ai_data_policy_summary,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="QuantIQ AI Data Analyst",
    description=(
        "AI-powered data analyst supporting "
        "CSV, Excel, MySQL, and extensible "
        "database sources."
    ),
    version="1.2.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# GLOBAL SOURCE STATE
# ============================================================

_active_source = "none"


_uploaded_datasets: Dict[
    str,
    Dict[str, Any],
] = {}


_current_dataset: Optional[str] = None


# ============================================================
# MYSQL STATE
# ============================================================

_mysql_connection = None

_mysql_config: Optional[
    Dict[str, Any]
] = None


# ============================================================
# REQUEST MODELS
# ============================================================

class ConversationMessage(BaseModel):

    role: str

    content: str = ""

    sql: Optional[
        Any
    ] = None


class QueryRequest(BaseModel):

    question: str

    conversation: List[
        ConversationMessage
    ] = Field(
        default_factory=list
    )


class MySQLConnectRequest(BaseModel):

    host: str = "localhost"

    port: int = 3306

    username: str = "root"

    password: str = ""

    database: Optional[str] = None


class MySQLSelectDatabaseRequest(BaseModel):

    database: str


class DatabaseSelectRequest(BaseModel):

    database: str


# ============================================================
# JSON SAFETY
# ============================================================

def _filter_schema_payload_for_ui(
    schema: Any,
) -> Any:
    """
    Remove protected tables/columns before schema metadata reaches the UI.

    The AI schema filter protects Gemini. This second layer prevents the UI
    schema endpoints from exposing protected objects unnecessarily.
    """
    if isinstance(schema, list):
        filtered = []

        for item in schema:
            if isinstance(item, str):
                if not is_table_blocked(item) and not is_column_blocked("", item):
                    filtered.append(item)
                continue

            if isinstance(item, dict):
                item_copy = dict(item)
                table_name = (
                    item_copy.get("table")
                    or item_copy.get("table_name")
                    or item_copy.get("name")
                )

                if table_name and is_table_blocked(str(table_name)):
                    continue

                for key in ("column", "column_name", "name"):
                    if key in item_copy and isinstance(item_copy[key], str):
                        if is_column_blocked(
                            str(table_name or ""),
                            item_copy[key],
                        ):
                            item_copy.pop(key, None)

                filtered.append(item_copy)
                continue

            filtered.append(item)

        return filtered

    if not isinstance(schema, dict):
        return schema

    result = {}

    for key, value in schema.items():
        if isinstance(key, str) and is_table_blocked(key):
            continue

        if isinstance(value, dict):
            table_name = str(key) if isinstance(key, str) else ""
            value_copy = dict(value)

            for container_key in ("columns", "schema", "fields"):
                if container_key not in value_copy:
                    continue

                container = value_copy[container_key]

                if isinstance(container, dict):
                    value_copy[container_key] = {
                        column_name: column_value
                        for column_name, column_value in container.items()
                        if not is_column_blocked(
                            table_name,
                            str(column_name),
                        )
                    }

                elif isinstance(container, list):
                    filtered_container = []

                    for column in container:
                        if isinstance(column, str):
                            if not is_column_blocked(table_name, column):
                                filtered_container.append(column)
                        elif isinstance(column, dict):
                            column_copy = dict(column)
                            column_name = (
                                column_copy.get("name")
                                or column_copy.get("column")
                                or column_copy.get("column_name")
                            )

                            if column_name and is_column_blocked(
                                table_name,
                                str(column_name),
                            ):
                                continue

                            filtered_container.append(column_copy)
                        else:
                            filtered_container.append(column)

                    value_copy[container_key] = filtered_container

            result[key] = value_copy
            continue

        if isinstance(value, list) and isinstance(key, str):
            result[key] = [
                item
                for item in value
                if not (
                    isinstance(item, str)
                    and is_column_blocked(key, item)
                )
            ]
        else:
            result[key] = value

    return result


def make_json_safe(
    value: Any,
) -> Any:

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key): make_json_safe(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return [
            make_json_safe(item)
            for item in value
        ]

    return str(value)


# ============================================================
# ACTIVE SOURCE
# ============================================================

def get_active_source() -> str:

    return _active_source


def set_active_source(
    source: str,
) -> None:

    global _active_source

    allowed_sources = {
        "none",
        "file",
        "mysql",
        "postgresql",
        "sqlserver",
        "sqlite",
    }

    if source not in allowed_sources:

        raise ValueError(
            f"Invalid source: {source}"
        )

    _active_source = source


# ============================================================
# MYSQL CONNECTION
# ============================================================

def mysql_is_connected() -> bool:
    """
    Check whether the current MySQL connection is usable.

    mysql.connector connections can become stale while the Python
    connection object still exists. This commonly happens after an
    idle timeout, MySQL restart, network interruption, laptop sleep,
    or temporary connection loss.

    We therefore actively PING the server and allow the connector to
    reconnect. If that fails, QuantIQ attempts a fresh connection
    using the stored connection configuration.

    This function never changes the active source to "none" merely
    because a transient connection failure occurred.
    """

    global _mysql_connection

    if not _mysql_config:
        return False

    if _mysql_connection is not None:

        try:

            ping = getattr(
                _mysql_connection,
                "ping",
                None,
            )

            if callable(ping):

                ping(
                    reconnect=True,
                    attempts=3,
                    delay=1,
                )

                if _mysql_connection.is_connected():
                    return True

            elif hasattr(
                _mysql_connection,
                "is_connected",
            ):

                if _mysql_connection.is_connected():
                    return True

        except Exception:

            # The existing connection is stale or unusable.
            # Fall through to a completely new connection.
            pass

    # ------------------------------------------------------------
    # FRESH CONNECTION
    # ------------------------------------------------------------

    try:

        connection = create_connection(
            host=_mysql_config.get("host"),
            port=int(
                _mysql_config.get(
                    "port",
                    3306,
                )
            ),
            username=_mysql_config.get(
                "username",
            ),
            password=_mysql_config.get(
                "password",
                "",
            ),
            database=_mysql_config.get(
                "database",
            ),
        )

        _mysql_connection = connection

        return bool(
            _mysql_connection.is_connected()
        )

    except Exception:

        return False


def safe_mysql_config():

    if not _mysql_config:
        return None

    return {
        "host":
            _mysql_config.get(
                "host"
            ),

        "port":
            _mysql_config.get(
                "port"
            ),

        "username":
            _mysql_config.get(
                "username"
            ),

        "database":
            _mysql_config.get(
                "database"
            ),

        "connected":
            mysql_is_connected(),
    }


def disconnect_mysql():

    global _mysql_connection
    global _mysql_config

    if _mysql_connection is not None:

        try:

            _mysql_connection.close()

        except Exception:

            pass

    _mysql_connection = None

    _mysql_config = None


# ============================================================
# FILE DATASET HELPERS
# ============================================================

def get_current_dataset():

    if not _current_dataset:
        return None

    return _uploaded_datasets.get(
        _current_dataset
    )


def get_current_dataset_name():

    return _current_dataset


# ============================================================
# SAFE IDENTIFIER
# ============================================================

def make_safe_identifier(
    value: str,
    fallback: str = "table",
) -> str:

    value = str(
        value or ""
    ).strip()

    value = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        value,
    )

    value = re.sub(
        r"_+",
        "_",
        value,
    )

    value = value.strip(
        "_"
    )

    if not value:
        return fallback

    if value[0].isdigit():

        value = (
            f"table_{value}"
        )

    return value


# ============================================================
# FILE SCHEMA CONTEXT
# ============================================================

def get_file_schema_context(
    dataset: Dict[str, Any],
) -> str:

    lines = []

    lines.append(
        "SOURCE: uploaded files"
    )

    lines.append(
        "DIALECT: DuckDB"
    )

    lines.append("")

    tables = dataset.get(
        "tables",
        {},
    )

    lines.append(
        "TABLES:"
    )

    for table_name in tables.keys():

        lines.append(
            f'- "{table_name}"'
        )

    lines.append("")

    lines.append(
        "COLUMNS:"
    )

    for (
        table_name,
        table_info,
    ) in tables.items():

        lines.append("")

        lines.append(
            f'TABLE "{table_name}":'
        )

        schema = table_info.get(
            "schema",
            {},
        )

        columns = schema.get(
            "columns",
            [],
        )

        for column in columns:

            if isinstance(
                column,
                dict,
            ):

                name = column.get(
                    "name",
                    "",
                )

                dtype = column.get(
                    "type",
                    "VARCHAR",
                )

                lines.append(
                    f'- "{name}" ({dtype})'
                )

            else:

                lines.append(
                    f'- "{column}"'
                )

    return "\n".join(
        lines
    )


# ============================================================
# CSV READER
# ============================================================

def read_csv_with_encoding_fallback(
    file_path: str,
):

    if pd is None:

        raise RuntimeError(
            "Pandas is not installed."
        )

    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
    ]

    last_error = None

    for encoding in encodings:

        try:

            return pd.read_csv(
                file_path,
                encoding=encoding,
            )

        except UnicodeDecodeError as exc:

            last_error = exc

    if last_error:

        raise last_error

    raise RuntimeError(
        "Could not read CSV file."
    )


# ============================================================
# DATAFRAME NORMALIZATION
# ============================================================

def normalize_dataframe(
    dataframe,
):

    dataframe = dataframe.copy()

    original_columns = [
        str(column).strip()
        for column
        in dataframe.columns
    ]

    used = {}

    final_columns = []

    for column in original_columns:

        if column not in used:

            used[column] = 0

            final_columns.append(
                column
            )

        else:

            used[column] += 1

            final_columns.append(
                f"{column}_{used[column]}"
            )

    dataframe.columns = (
        final_columns
    )

    return dataframe


# ============================================================
# REGISTER UPLOADED DATASET
# ============================================================

def register_uploaded_dataset(
    dataset_name: str,
    files_data: List[
        Dict[str, Any]
    ],
):

    if duckdb is None:

        raise RuntimeError(
            "DuckDB is not installed."
        )

    connection = duckdb.connect(
        database=":memory:"
    )

    tables = {}

    dataframes = {}

    for file_data in files_data:

        table_name = file_data[
            "table_name"
        ]

        dataframe = file_data[
            "dataframe"
        ]

        original_filename = file_data[
            "original_filename"
        ]

        connection.register(
            table_name,
            dataframe,
        )

        describe_sql = (
            f'DESCRIBE "{table_name}"'
        )

        rows = connection.execute(
            describe_sql
        ).fetchall()

        columns = []

        for row in rows:

            columns.append(
                {
                    "name": row[0],
                    "type": row[1],
                }
            )

        tables[table_name] = {

            "table_name":
                table_name,

            "original_filename":
                original_filename,

            "dataframe":
                dataframe,

            "schema": {
                "columns": columns
            },
        }

        dataframes[
            table_name
        ] = dataframe

    dataset = {

        "name":
            dataset_name,

        "tables":
            tables,

        "dataframes":
            dataframes,

        "connection":
            connection,

        "original_files": [
            item[
                "original_filename"
            ]
            for item
            in files_data
        ],
    }

    _uploaded_datasets[
        dataset_name
    ] = dataset

    return dataset


# ============================================================
# DUCKDB QUERY
# ============================================================

def execute_duckdb_query(
    dataset: Dict[str, Any],
    sql: str,
) -> Dict[str, Any]:

    if duckdb is None:

        raise RuntimeError(
            "DuckDB is not installed."
        )

    connection = dataset.get(
        "connection"
    )

    if connection is None:

        raise RuntimeError(
            "Dataset has no DuckDB connection."
        )

    cursor = connection.execute(
        sql
    )

    description = cursor.description

    if description is None:

        return {
            "success": True,
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    columns = [
        item[0]
        for item in description
    ]

    rows = cursor.fetchall()

    result_rows = []

    for row in rows:

        result_rows.append(
            {
                columns[index]:
                    make_json_safe(
                        value
                    )
                for index, value
                in enumerate(row)
            }
        )

    return {
        "success": True,
        "columns": columns,
        "rows": result_rows,
        "row_count": len(
            result_rows
        ),
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "success": True,
        "name": "QuantIQ",
        "message": (
            "AI Data Analyst API is running."
        ),
        "active_source":
            get_active_source(),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "success": True,
        "status": "healthy",

        "source":
            get_active_source(),

        "active_source":
            get_active_source(),

        "mysql": {
            "connected":
                mysql_is_connected(),

            "host":
                (
                    _mysql_config.get(
                        "host"
                    )
                    if _mysql_config
                    else None
                ),

            "port":
                (
                    _mysql_config.get(
                        "port"
                    )
                    if _mysql_config
                    else None
                ),

            "username":
                (
                    _mysql_config.get(
                        "username"
                    )
                    if _mysql_config
                    else None
                ),

            "database":
                (
                    _mysql_config.get(
                        "database"
                    )
                    if _mysql_config
                    else None
                ),
        },

        "mysql_connected":
            mysql_is_connected(),

        "dataset":
            get_current_dataset_name(),

        "file_dataset":
            get_current_dataset_name(),
    }


# ============================================================
# DATABASE STATUS
# ============================================================

@app.get("/database")
def database_status():

    source = get_active_source()

    if source == "mysql":

        config = safe_mysql_config()

        return {
            "success": True,
            "source": "mysql",
            "connected":
                mysql_is_connected(),

            "host":
                (
                    config.get("host")
                    if config
                    else None
                ),

            "port":
                (
                    config.get("port")
                    if config
                    else None
                ),

            "username":
                (
                    config.get("username")
                    if config
                    else None
                ),

            "database":
                (
                    config.get("database")
                    if config
                    else None
                ),
        }

    if source == "file":

        dataset = (
            get_current_dataset()
        )

        return {
            "success": True,
            "source": "file",
            "connected":
                dataset is not None,

            "dataset":
                get_current_dataset_name(),
        }

    return {
        "success": True,
        "source": "none",
        "connected": False,
    }


# ============================================================
# MYSQL TEST
# ============================================================

@app.post("/mysql/test")
def mysql_test(
    request: MySQLConnectRequest,
):

    try:

        result = test_connection(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database=request.database,
        )

        result = make_json_safe(
            result
        )

        if isinstance(
            result,
            dict,
        ):

            if "success" not in result:

                result["success"] = bool(
                    result.get(
                        "connected",
                        False,
                    )
                )

            result["source"] = "mysql"

        return result

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL CONNECT
# ============================================================

@app.post("/mysql/connect")
def mysql_connect(
    request: MySQLConnectRequest,
):

    global _mysql_connection
    global _mysql_config
    global _current_dataset

    try:

        disconnect_mysql()

        connection = create_connection(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database=request.database,
        )

        _mysql_connection = (
            connection
        )

        _mysql_config = {

            "host":
                request.host,

            "port":
                request.port,

            "username":
                request.username,

            "password":
                request.password,

            "database":
                request.database,
        }

        _current_dataset = None

        set_active_source(
            "mysql"
        )

        return {
            "success": True,

            "message":
                "MySQL connection successful.",

            "source": "mysql",

            "active_source":
                "mysql",

            "connected": True,

            "host":
                request.host,

            "port":
                request.port,

            "username":
                request.username,

            "database":
                request.database,
        }

    except Exception as exc:

        disconnect_mysql()

        set_active_source(
            "none"
        )

        return {
            "success": False,
            "source": "none",
            "active_source": "none",
            "connected": False,
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL STATUS
# ============================================================

@app.get("/mysql/status")
def mysql_status():

    config = safe_mysql_config()

    return {
        "success": True,

        "source":
            (
                "mysql"
                if mysql_is_connected()
                else "none"
            ),

        "connected":
            mysql_is_connected(),

        "host":
            (
                config.get("host")
                if config
                else None
            ),

        "port":
            (
                config.get("port")
                if config
                else None
            ),

        "username":
            (
                config.get("username")
                if config
                else None
            ),

        "database":
            (
                config.get("database")
                if config
                else None
            ),
    }


# ============================================================
# MYSQL DISCONNECT
# ============================================================

@app.post("/mysql/disconnect")
def mysql_disconnect():

    disconnect_mysql()

    if get_current_dataset() is not None:

        set_active_source(
            "file"
        )

    else:

        set_active_source(
            "none"
        )

    return {
        "success": True,
        "message":
            "MySQL disconnected.",
        "active_source":
            get_active_source(),
        "source":
            get_active_source(),
    }


# ============================================================
# GENERIC DISCONNECT
# ============================================================

@app.post("/disconnect")
def disconnect():

    global _current_dataset

    disconnect_mysql()

    _current_dataset = None

    set_active_source(
        "none"
    )

    return {
        "success": True,
        "message":
            "Data source disconnected.",
        "active_source":
            "none",
        "source":
            "none",
    }


# ============================================================
# MYSQL DATABASES
# ============================================================

@app.get("/mysql/databases")
def mysql_databases():

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    try:

        databases = list_databases(
            _mysql_connection
        )

        return {
            "success": True,
            "source": "mysql",

            "databases":
                make_json_safe(
                    databases
                ),
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL SELECT DATABASE
# ============================================================

@app.post(
    "/mysql/select-database"
)
def mysql_select_database(
    request:
        MySQLSelectDatabaseRequest,
):

    global _mysql_config
    global _current_dataset

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    database = (
        request.database.strip()
    )

    if not database:

        raise HTTPException(
            status_code=400,
            detail=(
                "Database name is required."
            ),
        )

    try:

        cursor = (
            _mysql_connection.cursor()
        )

        safe_database = (
            database.replace(
                "`",
                "``",
            )
        )

        cursor.execute(
            f"USE `{safe_database}`"
        )

        cursor.close()

        if _mysql_config is None:
            _mysql_config = {}

        _mysql_config[
            "database"
        ] = database

        _current_dataset = None

        set_active_source(
            "mysql"
        )

        return {
            "success": True,

            "message":
                (
                    f"Database "
                    f"'{database}' selected."
                ),

            "source":
                "mysql",

            "active_source":
                "mysql",

            "database":
                database,
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL TABLES
# ============================================================

@app.get("/mysql/tables")
def mysql_tables():

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    try:

        database = (
            _mysql_config.get(
                "database"
            )
            if _mysql_config
            else None
        )

        tables = list_tables(
            _mysql_connection,
            database=database,
        )

        safe_tables = [
            table
            for table in tables
            if not is_table_blocked(str(table))
        ]

        return {
            "success": True,
            "source": "mysql",
            "database":
                database,

            "tables":
                make_json_safe(
                    safe_tables
                ),
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL SCHEMA
# ============================================================

@app.get("/mysql/schema")
def mysql_schema():

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    try:

        database = (
            _mysql_config.get(
                "database"
            )
            if _mysql_config
            else None
        )

        schema = get_schema(
            _mysql_connection,
            database=database,
        )

        context = (
            build_schema_context(
                _mysql_connection,
                database=database,
            )
        )

        safe_schema = _filter_schema_payload_for_ui(schema)

        safe_context, _schema_security_report = filter_schema_text(
            context
        )

        return {
            "success": True,
            "source": "mysql",
            "database":
                database,

            "schema":
                make_json_safe(
                    safe_schema
                ),

            "context":
                safe_context,
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL VALUES
# ============================================================

@app.get("/mysql/values")
def mysql_values(
    table: str,
    column: str,
    limit: int = 20,
):

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    try:

        if is_table_blocked(table):
            raise PermissionError(
                f"Access to protected table '{table}' is blocked."
            )

        if is_column_blocked(table, column):
            raise PermissionError(
                f"Access to protected column '{column}' is blocked."
            )

        safe_limit = max(1, min(int(limit), 100))

        values = (
            get_database_values(
                _mysql_connection,
                table=table,
                column=column,
                limit=safe_limit,
            )
        )

        return {
            "success": True,
            "source": "mysql",
            "table": table,
            "column": column,

            "values":
                make_json_safe(
                    values
                ),
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# MYSQL RAW QUERY
# ============================================================

@app.post("/mysql/query")
def mysql_raw_query(
    request: QueryRequest,
):

    if not mysql_is_connected():

        raise HTTPException(
            status_code=400,
            detail=(
                "MySQL is not connected."
            ),
        )

    sql = (
        request.question.strip()
    )

    if not sql:

        raise HTTPException(
            status_code=400,
            detail=(
                "SQL query is required."
            ),
        )

    try:

        validate_read_only_sql(
            sql
        )

        validate_generated_queries(
            [{"sql": sql}]
        )

        result = execute_query(
            _mysql_connection,
            sql,
        )

        return make_json_safe(
            result
        )

    except Exception as exc:

        return {
            "success": False,
            "source": "mysql",
            "message":
                clean_mysql_error(
                    exc
                ),
        }


# ============================================================
# FILE UPLOAD
# ============================================================

@app.post("/upload")
async def upload_file(
    source_type: str = Form(...),
    files: List[
        UploadFile
    ] = File(...),
):

    global _current_dataset

    source_type = (
        source_type or ""
    ).strip().lower()

    if source_type not in {
        "csv",
        "excel",
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Supported file sources "
                "are CSV and Excel."
            ),
        )

    if not files:

        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload at least one file."
            ),
        )

    if pd is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "Pandas is not installed."
            ),
        )

    files_data = []

    try:

        for uploaded_file in files:

            filename = (
                uploaded_file.filename
                or ""
            )

            extension = (
                os.path.splitext(
                    filename
                )[1].lower()
            )

            if extension not in {
                ".csv",
                ".xlsx",
                ".xls",
                ".xlsm",
            }:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported file type: "
                        f"{filename}"
                    ),
                )

            contents = (
                await uploaded_file.read()
            )

            if not contents:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File '{filename}' "
                        f"is empty."
                    ),
                )

            safe_filename = re.sub(
                r"[^a-zA-Z0-9_.-]",
                "_",
                filename,
            )

            temp_path = os.path.join(
                os.getcwd(),
                f".quantiq_{safe_filename}",
            )

            try:

                with open(
                    temp_path,
                    "wb",
                ) as output_file:

                    output_file.write(
                        contents
                    )

                if extension == ".csv":

                    dataframe = (
                        read_csv_with_encoding_fallback(
                            temp_path
                        )
                    )

                else:

                    dataframe = (
                        pd.read_excel(
                            temp_path
                        )
                    )

            finally:

                try:
                    os.remove(
                        temp_path
                    )
                except Exception:
                    pass

            dataframe = (
                normalize_dataframe(
                    dataframe
                )
            )

            base_name = (
                os.path.splitext(
                    filename
                )[0]
            )

            table_name = (
                make_safe_identifier(
                    base_name,
                    fallback="data",
                )
            )

            existing_names = {
                item["table_name"]
                for item
                in files_data
            }

            original_table_name = (
                table_name
            )

            counter = 2

            while (
                table_name
                in existing_names
            ):

                table_name = (
                    f"{original_table_name}"
                    f"_{counter}"
                )

                counter += 1

            files_data.append(
                {
                    "table_name":
                        table_name,

                    "dataframe":
                        dataframe,

                    "original_filename":
                        filename,
                }
            )

        if len(files_data) == 1:

            dataset_name = (
                os.path.splitext(
                    files_data[0][
                        "original_filename"
                    ]
                )[0]
            )

        else:

            dataset_name = (
                f"uploaded_dataset_"
                f"{len(_uploaded_datasets) + 1}"
            )

        dataset_name = (
            dataset_name.strip()
            or
            f"dataset_"
            f"{len(_uploaded_datasets) + 1}"
        )

        disconnect_mysql()

        dataset = (
            register_uploaded_dataset(
                dataset_name=
                    dataset_name,
                files_data=
                    files_data,
            )
        )

        _current_dataset = (
            dataset_name
        )

        set_active_source(
            "file"
        )

        total_rows = 0

        all_columns = []

        table_response = []

        for (
            table_name,
            table_info,
        ) in dataset[
            "tables"
        ].items():

            dataframe = (
                table_info[
                    "dataframe"
                ]
            )

            row_count = len(
                dataframe
            )

            total_rows += (
                row_count
            )

            columns = list(
                dataframe.columns
            )

            all_columns.extend(
                columns
            )

            table_response.append(
                {
                    "table":
                        table_name,

                    "filename":
                        table_info[
                            "original_filename"
                        ],

                    "rows":
                        row_count,

                    "columns":
                        columns,
                }
            )

        return {
            "success": True,

            "message":
                "File upload successful.",

            "source":
                "file",

            "active_source":
                "file",

            "dataset":
                dataset_name,

            "files": [
                item[
                    "original_filename"
                ]
                for item
                in files_data
            ],

            "tables":
                table_response,

            "table":
                (
                    table_response[0][
                        "table"
                    ]
                    if len(
                        table_response
                    ) == 1
                    else None
                ),

            "filename":
                (
                    files_data[0][
                        "original_filename"
                    ]
                    if len(
                        files_data
                    ) == 1
                    else None
                ),

            "rows":
                total_rows,

            "columns":
                list(
                    dict.fromkeys(
                        all_columns
                    )
                ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        traceback.print_exc()

        return {
            "success": False,
            "source": "file",
            "message":
                str(exc),
        }


# ============================================================
# DATASETS
# ============================================================

@app.get("/datasets")
def datasets():

    output = []

    for (
        name,
        dataset,
    ) in _uploaded_datasets.items():

        tables = dataset.get(
            "tables",
            {},
        )

        total_rows = 0

        all_columns = []

        table_output = []

        for (
            table_name,
            table_info,
        ) in tables.items():

            dataframe = (
                table_info.get(
                    "dataframe"
                )
            )

            rows = (
                len(dataframe)
                if dataframe is not None
                else 0
            )

            columns = (
                list(
                    dataframe.columns
                )
                if dataframe is not None
                else []
            )

            total_rows += rows

            all_columns.extend(
                columns
            )

            table_output.append(
                {
                    "table":
                        table_name,

                    "filename":
                        table_info.get(
                            "original_filename"
                        ),

                    "rows":
                        rows,

                    "columns":
                        columns,
                }
            )

        output.append(
            {
                "name":
                    name,

                "files":
                    dataset.get(
                        "original_files",
                        [],
                    ),

                "tables":
                    table_output,

                "rows":
                    total_rows,

                "columns":
                    list(
                        dict.fromkeys(
                            all_columns
                        )
                    ),

                "active":
                    (
                        name ==
                        _current_dataset
                        and
                        get_active_source()
                        == "file"
                    ),
            }
        )

    return {
        "success": True,
        "datasets": output,
    }


# ============================================================
# SELECT DATASET
# ============================================================

@app.post(
    "/datasets/select"
)
def select_dataset(
    request:
        DatabaseSelectRequest,
):

    global _current_dataset

    dataset_name = (
        request.database.strip()
    )

    if (
        dataset_name
        not in _uploaded_datasets
    ):

        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset not found."
            ),
        )

    disconnect_mysql()

    _current_dataset = (
        dataset_name
    )

    set_active_source(
        "file"
    )

    return {
        "success": True,

        "message":
            (
                f"Dataset "
                f"'{dataset_name}' selected."
            ),

        "dataset":
            dataset_name,

        "source":
            "file",

        "active_source":
            "file",
    }


# ============================================================
# FILE SCHEMA
# ============================================================

@app.get("/schema")
def file_schema():

    if (
        get_active_source()
        != "file"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "No file dataset is active."
            ),
        )

    dataset = (
        get_current_dataset()
    )

    if dataset is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "No active dataset found."
            ),
        )

    return {
        "success": True,

        "source":
            "file",

        "dataset":
            get_current_dataset_name(),

        "tables":
            [
                table_name
                for table_name
                in dataset.get(
                    "tables",
                    {},
                ).keys()
                if not is_table_blocked(str(table_name))
            ],

        "schema":
            make_json_safe(
                _filter_schema_payload_for_ui(
                    {
                        table_name:
                            table_info.get(
                                "schema",
                                {},
                            )
                        for (
                            table_name,
                            table_info,
                        )
                        in dataset.get(
                            "tables",
                            {},
                        ).items()
                    }
                )
            ),

        "context":
            get_file_schema_context(
                dataset
            ),
    }


# ============================================================
# ACTIVE SCHEMA CONTEXT
# ============================================================

def get_active_schema_context() -> str:

    source = (
        get_active_source()
    )

    # --------------------------------------------------------
    # MYSQL
    # --------------------------------------------------------

    if source == "mysql":

        if not mysql_is_connected():

            raise RuntimeError(
                "MySQL is marked active "
                "but there is no active "
                "connection."
            )

        database = (
            _mysql_config.get(
                "database"
            )
            if _mysql_config
            else None
        )

        if not database:

            raise RuntimeError(
                "No MySQL database is selected."
            )

        return build_schema_context(
            _mysql_connection,
            database=database,
        )

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

    if source == "file":

        dataset = (
            get_current_dataset()
        )

        if dataset is None:

            raise RuntimeError(
                "No active file dataset."
            )

        return get_file_schema_context(
            dataset
        )

    raise RuntimeError(
        "No active data source."
    )


# ============================================================
# EXECUTE ANALYSIS
# ============================================================

def execute_analysis(
    analysis: Dict[str, Any],
    schema_context: str,
) -> Dict[str, Any]:

    source = (
        get_active_source()
    )

    # --------------------------------------------------------
    # MYSQL
    # --------------------------------------------------------

    if source == "mysql":

        if not mysql_is_connected():

            raise RuntimeError(
                "MySQL is not connected."
            )

        sql = generate_sql(
            analysis,
            schema_context=
                schema_context,
            dialect="mysql",
        )

        validate_read_only_sql(
            sql
        )

        validate_generated_queries(
            [{"sql": sql}]
        )

        result = execute_query(
            _mysql_connection,
            sql,
        )

        if not result.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "sql":
                    sql,

                "message":
                    result.get(
                        "message",
                        "MySQL execution failed.",
                    ),
            }

        return {
            "success":
                True,

            "sql":
                sql,

            "columns":
                result.get(
                    "columns",
                    [],
                ),

            "rows":
                make_json_safe(
                    result.get(
                        "rows",
                        [],
                    )
                ),

            "row_count":
                result.get(
                    "row_count",
                    0,
                ),
        }

    # --------------------------------------------------------
    # DUCKDB
    # --------------------------------------------------------

    if source == "file":

        dataset = (
            get_current_dataset()
        )

        if dataset is None:

            raise RuntimeError(
                "No active file dataset."
            )

        sql = generate_sql(
            analysis,
            schema_context=
                schema_context,
            dialect="duckdb",
        )

        validate_generated_queries(
            [{"sql": sql}]
        )

        result = (
            execute_duckdb_query(
                dataset,
                sql,
            )
        )

        return {
            "success":
                result.get(
                    "success",
                    False,
                ),

            "sql":
                sql,

            "columns":
                result.get(
                    "columns",
                    [],
                ),

            "rows":
                result.get(
                    "rows",
                    [],
                ),

            "row_count":
                result.get(
                    "row_count",
                    0,
                ),
        }

    raise RuntimeError(
        "Unsupported or inactive "
        "data source."
    )


# ============================================================
# MAIN AI QUERY
# ============================================================

@app.post("/query")
def query(
    request: QueryRequest,
):

    question = (
        request.question.strip()
    )

    if not question:

        raise HTTPException(
            status_code=400,
            detail=(
                "Question cannot be empty."
            ),
        )

    source = (
        get_active_source()
    )

    # --------------------------------------------------------
    # SOURCE VALIDATION
    # --------------------------------------------------------

    if source == "none":

        raise HTTPException(
            status_code=400,
            detail=(
                "No data source is active. "
                "Connect MySQL or upload "
                "CSV/Excel data."
            ),
        )

    if (
        source == "mysql"
        and
        not mysql_is_connected()
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "MySQL connection is unavailable. "
                "QuantIQ attempted to reconnect automatically. "
                "Please verify that the MySQL server is running "
                "and try again."
            ),
        )

    if (
        source == "file"
        and
        get_current_dataset() is None
    ):

        set_active_source(
            "none"
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "The active file dataset "
                "is no longer available."
            ),
        )

    try:

        # ====================================================
        # 1. FULL SCHEMA
        # ====================================================

        full_schema_context = (
            get_active_schema_context()
        )

        # ====================================================
        # 1A. SECURITY FILTER
        # ====================================================

        full_schema_context, security_report = (
            filter_schema_text(
                full_schema_context
            )
        )

        if not full_schema_context.strip():
            raise RuntimeError(
                "No AI-accessible schema remains after "
                "security filtering."
            )

        # ====================================================
        # 2. RELEVANT SCHEMA
        # ====================================================

        schema_context = (
            select_context(
                question=question,
                schema_context=
                    full_schema_context,
            )
        )

        # ====================================================
        # 3. CONVERSATION CONTEXT
        # ====================================================

        conversation_context = (
            build_conversation_context(
                [
                    message.model_dump()
                    for message
                    in request.conversation
                ]
            )
        )

        # ====================================================
        # 4. GEMINI PLANNER
        # ====================================================

        plan = create_plan(
            question=question,
            schema_context=
                schema_context,
            conversation_context=
                conversation_context,
        )

        if not isinstance(
            plan,
            dict,
        ):

            raise RuntimeError(
                "Planner returned an invalid plan."
            )

        # ====================================================
        # 5. ANALYSES
        # ====================================================

        analyses = plan.get(
            "analyses",
            [],
        )

        if not isinstance(
            analyses,
            list,
        ):

            raise RuntimeError(
                "Planner returned an invalid "
                "analyses list."
            )

        if not analyses:

            raise RuntimeError(
                "Planner returned no analyses."
            )

        # ====================================================
        # 6. EXECUTE ANALYSES
        # ====================================================

        results = []

        for (
            index,
            analysis,
        ) in enumerate(
            analyses
        ):

            if not isinstance(
                analysis,
                dict,
            ):

                raise RuntimeError(
                    "Planner returned an "
                    "invalid analysis."
                )

            execution = (
                execute_analysis(
                    analysis=
                        analysis,

                    schema_context=
                        schema_context,
                )
            )

            if not execution.get(
                "success",
                False,
            ):

                raise RuntimeError(
                    execution.get(
                        "message",
                        "Database execution failed.",
                    )
                )

            results.append(
                {
                    "analysis_index":
                        index,

                    "analysis":
                        analysis,

                    "sql":
                        execution.get(
                            "sql"
                        ),

                    "success":
                        True,

                    "columns":
                        execution.get(
                            "columns",
                            [],
                        ),

                    "rows":
                        execution.get(
                            "rows",
                            [],
                        ),

                    "row_count":
                        execution.get(
                            "row_count",
                            0,
                        ),
                }
            )

        # ====================================================
        # 7. AI DATA BOUNDARY
        # ====================================================
        #
        # IMPORTANT:
        # `results` remains the full verified database result
        # for the QuantIQ UI.
        #
        # A separate filtered copy is created for the Answer
        # Agent. This prevents raw/sensitive result data from
        # automatically reaching Gemini.
        # ====================================================

        ai_safe_results = filter_results_for_ai(
            results=results,
            query_plan=plan,
        )

        # ====================================================
        # 8. GROUNDED ANSWER AGENT
        # ====================================================

        answer = generate_answer(
            question=question,

            query_plan=plan,

            results=ai_safe_results,

            semantic_context=
                schema_context,
        )

        # ====================================================
        # 8. FINAL RESPONSE
        # ====================================================

        return {
            "success":
                True,

            "source":
                source,

            "question":
                question,

            "answer":
                answer,

            "plan":
                make_json_safe(
                    plan
                ),

            "results":
                make_json_safe(
                    results
                ),

            "security":
                make_json_safe(
                    security_report
                ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        traceback.print_exc()

        return {
            "success":
                False,

            "source":
                source,

            "question":
                question,

            "error":
                str(exc),
        }


# ============================================================
# SECURITY CONFIGURATION
# ============================================================

@app.get("/security/config")
def security_config():

    return {
        "success": True,
        "security":
            get_security_summary(),
        "ai_data_policy":
            get_ai_data_policy_summary(),
    }


# ============================================================
# AI DATA SECURITY POLICY
# ============================================================

@app.get("/security/ai-data-policy")
def ai_data_policy():

    return {
        "success": True,
        "ai_data_policy":
            get_ai_data_policy_summary(),
    }


# ============================================================
# AVAILABLE SOURCES
# ============================================================

@app.get("/sources")
def available_sources():

    return {
        "success": True,

        "active_source":
            get_active_source(),

        "sources": [

            {
                "id":
                    "csv",

                "name":
                    "CSV",

                "type":
                    "file",

                "available":
                    True,
            },

            {
                "id":
                    "excel",

                "name":
                    "Excel",

                "type":
                    "file",

                "available":
                    True,
            },

            {
                "id":
                    "mysql",

                "name":
                    "MySQL",

                "type":
                    "database",

                "available":
                    True,
            },

            {
                "id":
                    "postgresql",

                "name":
                    "PostgreSQL",

                "type":
                    "database",

                "available":
                    False,

                "status":
                    "adapter_not_configured",
            },

            {
                "id":
                    "sqlserver",

                "name":
                    "SQL Server",

                "type":
                    "database",

                "available":
                    False,

                "status":
                    "adapter_not_configured",
            },

            {
                "id":
                    "sqlite",

                "name":
                    "SQLite",

                "type":
                    "database",

                "available":
                    False,

                "status":
                    "adapter_not_configured",
            },
        ],
    }


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event(
    "shutdown"
)
def shutdown_event():

    disconnect_mysql()

    for dataset in (
        _uploaded_datasets.values()
    ):

        connection = (
            dataset.get(
                "connection"
            )
        )

        if connection is not None:

            try:

                connection.close()

            except Exception:

                pass


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )