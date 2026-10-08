import pandas as pd
import sqlite3
from pathlib import Path


DATA_FOLDER = Path("data")
DATABASE_FILE = "database.db"


def load_csv_files():
    connection = sqlite3.connect(DATABASE_FILE)

    csv_files = list(DATA_FOLDER.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in the data folder.")
        connection.close()
        return

    for csv_file in csv_files:

        print(f"Loading: {csv_file.name}")

    try:
        df = pd.read_csv(csv_file, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_file, encoding="latin1")

        table_name = csv_file.stem

        df.to_sql(
            table_name,
            connection,
            if_exists="replace",
            index=False
        )

        print(
            f"Created table '{table_name}' "
            f"with {len(df)} rows and {len(df.columns)} columns."
        )

    connection.close()

    print("\nAll CSV files loaded successfully.")
    print(f"Database created: {DATABASE_FILE}")


if __name__ == "__main__":
    load_csv_files()