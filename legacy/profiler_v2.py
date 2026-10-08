from pathlib import Path
import json

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FOLDER = BASE_DIR / "data"
OUTPUT_FILE = BASE_DIR / "metadata_v2.json"

DATA_FOLDER.mkdir(exist_ok=True)


# ============================================================
# DETECT COLUMN TYPE
# ============================================================

def detect_column_type(series):

    # Numeric
    if pd.api.types.is_numeric_dtype(series):

        return "numeric"

    # Date detection
    sample = (
        series
        .dropna()
        .astype(str)
        .head(100)
    )

    if len(sample) > 0:

        parsed = pd.to_datetime(
            sample,
            errors="coerce",
            format="mixed"
        )

        if parsed.notna().mean() > 0.8:

            return "date"

    return "categorical"


# ============================================================
# PROFILE COLUMN
# ============================================================

def profile_column(series):

    row_count = len(series)

    null_count = int(
        series.isna().sum()
    )

    non_null = series.dropna()

    unique_count = int(
        non_null.nunique()
    )

    unique_ratio = (
        unique_count / len(non_null)
        if len(non_null) > 0
        else 0
    )

    column_type = detect_column_type(
        series
    )

    profile = {

        "type": column_type,

        "data_type": str(
            series.dtype
        ),

        "row_count": row_count,

        "null_count": null_count,

        "unique_count": unique_count,

        "unique_ratio": round(
            unique_ratio,
            4
        ),

        "repetition_ratio": round(
            1 - unique_ratio,
            4
        ),

        "sample_values": [
            str(value)
            for value in non_null.head(5)
        ]
    }

    # ========================================================
    # NUMERIC STATISTICS
    # ========================================================

    if column_type == "numeric":

        profile["statistics"] = {

            "min": (
                float(non_null.min())
                if len(non_null)
                else None
            ),

            "max": (
                float(non_null.max())
                if len(non_null)
                else None
            ),

            "mean": (
                float(non_null.mean())
                if len(non_null)
                else None
            ),

            "sum": (
                float(non_null.sum())
                if len(non_null)
                else None
            )
        }

    # ========================================================
    # STRUCTURAL PATTERN
    # ========================================================

    if unique_ratio >= 0.99:

        profile[
            "structural_pattern"
        ] = "mostly_unique"

    elif unique_ratio <= 0.05:

        profile[
            "structural_pattern"
        ] = "highly_repeated"

    else:

        profile[
            "structural_pattern"
        ] = "repeated"

    return profile


# ============================================================
# PROFILE DATASET
# ============================================================

def profile_dataset(csv_file):

    df = pd.read_csv(
        csv_file,
        encoding="latin1"
    )

    dataset = {

        "file": csv_file.name,

        "row_count": len(df),

        "column_count": len(
            df.columns
        ),

        "columns": {}
    }

    for column in df.columns:

        dataset[
            "columns"
        ][column] = profile_column(
            df[column]
        )

    return dataset


# ============================================================
# RUN PROFILER
# ============================================================

def run_profiler():

    csv_files = list(
        DATA_FOLDER.glob("*.csv")
    )

    if not csv_files:

        raise ValueError(
            "No CSV files found in the data folder."
        )

    metadata = {}

    for csv_file in csv_files:

        print(
            f"Profiling: {csv_file.name}"
        )

        metadata[
            csv_file.stem
        ] = profile_dataset(
            csv_file
        )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4
        )

    print(
        f"Metadata saved to: {OUTPUT_FILE}"
    )

    return metadata


# ============================================================
# MAIN
# ============================================================

def main():

    run_profiler()


if __name__ == "__main__":

    main()