"""
QuantIQ dataset manager.

Uploaded CSV/Excel files are converted into isolated SQLite databases.

IMPORTANT:
There is NO default automobile dataset.
The application starts with no dataset connected.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATASETS_DIR = DATA_DIR / "datasets"

REGISTRY_PATH = DATA_DIR / "datasets.json"
ACTIVE_PATH = DATA_DIR / "active_dataset.json"

# The old database.db is NOT used as a default dataset.
DEFAULT_DATABASE_PATH = BASE_DIR / "database.db"

DATA_DIR.mkdir(exist_ok=True)
DATASETS_DIR.mkdir(exist_ok=True)


# ============================================================
# JSON HELPERS
# ============================================================

def _read_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def _write_json(path: Path, value):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def _utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# REGISTRY
# ============================================================

def _registry():
    items = _read_json(
        REGISTRY_PATH,
        []
    )

    if not isinstance(items, list):
        return []

    # Remove the old automobile dataset completely.
    cleaned = [
        item
        for item in items
        if item.get("id") != "local-automobile"
    ]

    if cleaned != items:
        _save_registry(cleaned)

    return cleaned


def _save_registry(items):
    _write_json(
        REGISTRY_PATH,
        items
    )


# ============================================================
# REMOVE OLD AUTOMOBILE STATE
# ============================================================

def _remove_old_default_dataset():
    """
    Removes the old automobile dataset from registry/state.

    This is important because previous versions of QuantIQ
    automatically registered database.db as automobile_dataset.
    """

    items = _read_json(
        REGISTRY_PATH,
        []
    )

    if isinstance(items, list):
        cleaned = [
            item
            for item in items
            if item.get("id") != "local-automobile"
        ]

        if cleaned != items:
            _save_registry(cleaned)

    active = _read_json(
        ACTIVE_PATH,
        None
    )

    if (
        isinstance(active, dict)
        and active.get("id") == "local-automobile"
    ):
        ACTIVE_PATH.unlink(
            missing_ok=True
        )


_remove_old_default_dataset()


# ============================================================
# ACTIVE DATASET
# ============================================================

def get_active_dataset():
    """
    Return the currently active uploaded dataset.

    Returns None when no dataset has been uploaded.
    """

    active = _read_json(
        ACTIVE_PATH,
        None
    )

    if not isinstance(active, dict):
        return None

    dataset_id = active.get("id")

    if not dataset_id:
        return None

    if dataset_id == "local-automobile":
        ACTIVE_PATH.unlink(
            missing_ok=True
        )
        return None

    path_value = active.get("path")

    if not path_value:
        return None

    path = Path(
        path_value
    )

    if not path.exists():
        ACTIVE_PATH.unlink(
            missing_ok=True
        )
        return None

    return active


def set_active_dataset(dataset_id: str):
    items = _registry()

    item = next(
        (
            x
            for x in items
            if x.get("id") == dataset_id
        ),
        None
    )

    if item is None:
        raise ValueError(
            f"Dataset not found: {dataset_id}"
        )

    if item.get("id") == "local-automobile":
        raise ValueError(
            "The old automobile dataset is not allowed."
        )

    path = Path(
        item.get("path", "")
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file does not exist: {path}"
        )

    _write_json(
        ACTIVE_PATH,
        item
    )

    return item


def get_active_database_path():
    active = get_active_dataset()

    if not active:
        return None

    return str(
        Path(
            active["path"]
        )
    )


# ============================================================
# DATASET LIST
# ============================================================

def list_datasets():
    items = _registry()
    active = get_active_dataset()

    result = []

    for item in items:

        if item.get("id") == "local-automobile":
            continue

        copy = dict(item)

        copy["active"] = bool(
            active
            and active.get("id") == item.get("id")
        )

        result.append(copy)

    return result


# ============================================================
# FILE HELPERS
# ============================================================

def _file_bytes(uploaded_file) -> bytes:

    if hasattr(
        uploaded_file,
        "file"
    ):
        current = uploaded_file.file.tell()

        uploaded_file.file.seek(0)

        data = uploaded_file.file.read()

        uploaded_file.file.seek(
            current
        )

        return data

    if hasattr(
        uploaded_file,
        "read"
    ):
        return uploaded_file.read()

    raise ValueError(
        "Unsupported uploaded file object."
    )


def _file_name(uploaded_file):

    return (
        getattr(
            uploaded_file,
            "filename",
            None
        )
        or getattr(
            uploaded_file,
            "name",
            "uploaded_file"
        )
    )


# ============================================================
# NAME CLEANING
# ============================================================

def _safe_name(
    value: str,
    fallback: str = "table"
):

    value = Path(
        str(value)
    ).stem

    value = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        value
    )

    value = re.sub(
        r"_+",
        "_",
        value
    )

    value = value.strip("_")

    return (
        value[:80]
        or fallback
    )


def _unique_table_name(
    connection,
    requested: str
):

    base = _safe_name(
        requested
    )

    name = base
    counter = 2

    while connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (name,)
    ).fetchone():

        name = (
            f"{base}_{counter}"
        )

        counter += 1

    return name


# ============================================================
# DATAFRAME NORMALIZATION
# ============================================================

def _normalize_dataframe(
    df: pd.DataFrame
):

    df = df.copy()

    columns = []
    used = set()

    for index, column in enumerate(
        df.columns
    ):

        name = str(
            column
        ).strip()

        if (
            not name
            or name.lower() == "nan"
        ):
            name = (
                f"column_{index + 1}"
            )

        name = re.sub(
            r"\s+",
            " ",
            name
        )

        original_name = name
        counter = 2

        while name in used:

            name = (
                f"{original_name}_{counter}"
            )

            counter += 1

        used.add(name)

        columns.append(name)

    df.columns = columns

    return df


# ============================================================
# EXCEL
# ============================================================

def _read_excel_tables(
    file_name: str,
    data: bytes
):

    from io import BytesIO

    workbook = pd.ExcelFile(
        BytesIO(data)
    )

    file_stem = _safe_name(
        file_name
    )

    tables = []

    for sheet_name in workbook.sheet_names:

        df = pd.read_excel(
            BytesIO(data),
            sheet_name=sheet_name
        )

        if (
            df.empty
            and len(df.columns) == 0
        ):
            continue

        clean_sheet_name = _safe_name(
            sheet_name,
            "sheet"
        )

        table_name = (
            f"{file_stem}__"
            f"{clean_sheet_name}"
        )

        tables.append(
            (
                table_name,
                df
            )
        )

    return tables


# ============================================================
# CSV
# ============================================================

def _read_csv_table(
    file_name: str,
    data: bytes
):

    from io import BytesIO

    try:

        df = pd.read_csv(
            BytesIO(data),
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            BytesIO(data),
            encoding="latin1"
        )

    if df.empty:

        raise ValueError(
            f"{file_name} is empty."
        )

    return [
        (
            _safe_name(
                file_name
            ),
            df
        )
    ]


# ============================================================
# CREATE UPLOADED DATASET
# ============================================================

def create_uploaded_dataset(
    uploaded_files: Iterable,
    source_type: str
):

    files = list(
        uploaded_files
    )

    if not files:

        raise ValueError(
            "No files were uploaded."
        )

    source_type = (
        str(source_type)
        .lower()
        .strip()
    )

    if source_type not in {
        "csv",
        "excel"
    }:

        raise ValueError(
            "Only CSV and Excel uploads are supported."
        )

    # --------------------------------------------------------
    # UNIQUE DATABASE
    # --------------------------------------------------------

    dataset_id = (
        uuid.uuid4()
        .hex[:12]
    )

    database_path = (
        DATASETS_DIR
        / f"{dataset_id}.db"
    )

    tables = []
    total_rows = 0

    # --------------------------------------------------------
    # READ FILES
    # --------------------------------------------------------

    for uploaded_file in files:

        file_name = _file_name(
            uploaded_file
        )

        data = _file_bytes(
            uploaded_file
        )

        extension = (
            Path(file_name)
            .suffix
            .lower()
        )

        # ============================
        # EXCEL
        # ============================

        if source_type == "excel":

            if extension not in {
                ".xlsx",
                ".xls",
                ".xlsm"
            }:

                raise ValueError(
                    f"{file_name} is not an Excel file."
                )

            tables.extend(
                _read_excel_tables(
                    file_name,
                    data
                )
            )

        # ============================
        # CSV
        # ============================

        elif source_type == "csv":

            if extension != ".csv":

                raise ValueError(
                    f"{file_name} is not a CSV file."
                )

            tables.extend(
                _read_csv_table(
                    file_name,
                    data
                )
            )

    if not tables:

        raise ValueError(
            "No readable tables were found."
        )

    # --------------------------------------------------------
    # CREATE SQLITE
    # --------------------------------------------------------

    connection = sqlite3.connect(
        database_path
    )

    try:

        for requested_table_name, dataframe in tables:

            dataframe = _normalize_dataframe(
                dataframe
            )

            table_name = _unique_table_name(
                connection,
                requested_table_name
            )

            dataframe.to_sql(
                table_name,
                connection,
                if_exists="replace",
                index=False
            )

            total_rows += len(
                dataframe
            )

        connection.commit()

    except Exception:

        connection.close()

        database_path.unlink(
            missing_ok=True
        )

        raise

    finally:

        connection.close()

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    if len(files) == 1:

        dataset_name = _file_name(
            files[0]
        )

    else:

        dataset_name = (
            f"{len(files)} uploaded files"
        )

    metadata = {

        "id": dataset_id,

        "name": dataset_name,

        "type": (
            "CSV"
            if source_type == "csv"
            else "Excel"
        ),

        "status": "Connected",

        "path": str(
            database_path
        ),

        "created_at": _utc_now(),

        "managed": True,

        "table_count": len(
            tables
        ),

        "row_count": total_rows,

        "files": [
            _file_name(file)
            for file in files
        ],
    }

    # --------------------------------------------------------
    # SAVE REGISTRY
    # --------------------------------------------------------

    items = _registry()

    # Remove any accidental old automobile entry.
    items = [
        item
        for item in items
        if item.get("id") != "local-automobile"
    ]

    items.append(
        metadata
    )

    _save_registry(
        items
    )

    # --------------------------------------------------------
    # MAKE ACTIVE
    # --------------------------------------------------------

    set_active_dataset(
        dataset_id
    )

    return metadata