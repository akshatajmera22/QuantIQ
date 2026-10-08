from pathlib import Path
import json

import pandas as pd


DATA_FOLDER = Path("data")
OUTPUT_FILE = Path("metadata.json")


def profile_csv(file_path):
    df = pd.read_csv(
        file_path,
        encoding="latin1"
    )

    profile = {
        "file": file_path.name,
        "rows": len(df),
        "columns": {}
    }

    for column in df.columns:

        series = df[column]

        unique_count = int(series.nunique(dropna=True))
        null_count = int(series.isna().sum())

        column_info = {
            "dtype": str(series.dtype),
            "rows": len(series),
            "unique_values": unique_count,
            "null_values": null_count,
            "unique_ratio": round(
                unique_count / len(series),
                4
            ) if len(series) else 0,
            "sample_values": [
                str(value)
                for value in series.dropna().head(5).tolist()
            ]
        }

        # Numeric statistics
        if pd.api.types.is_numeric_dtype(series):

            column_info["type"] = "numeric"

            column_info["min"] = (
                float(series.min())
                if not series.dropna().empty
                else None
            )

            column_info["max"] = (
                float(series.max())
                if not series.dropna().empty
                else None
            )

            column_info["mean"] = (
                float(series.mean())
                if not series.dropna().empty
                else None
            )

        # Date detection
        elif pd.api.types.is_datetime64_any_dtype(series):

            column_info["type"] = "date"

        else:

            # Try to detect dates without modifying the original data
            parsed_dates = pd.to_datetime(
                series.dropna().head(100),
                errors="coerce"
            )

            if len(parsed_dates) > 0:

                date_ratio = parsed_dates.notna().mean()

                if date_ratio > 0.8:
                    column_info["type"] = "date"
                else:
                    column_info["type"] = "categorical"

            else:
                column_info["type"] = "categorical"

        # Potential identifier
        if unique_count == len(series.dropna()):
            column_info["possible_identifier"] = True
        else:
            column_info["possible_identifier"] = False

        profile["columns"][column] = column_info

    return profile


def main():

    csv_files = list(DATA_FOLDER.glob("*.csv"))

    if not csv_files:

        print("No CSV files found.")

        return

    all_profiles = {}

    for csv_file in csv_files:

        print(f"Profiling: {csv_file.name}")

        profile = profile_csv(csv_file)

        all_profiles[csv_file.stem] = profile

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_profiles,
            file,
            indent=4
        )

    print("\nProfiling complete.")

    print(
        f"Metadata saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()