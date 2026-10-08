from pathlib import Path
from sqlalchemy import create_engine, inspect, text


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"

engine = create_engine(
    f"sqlite:///{DATABASE_PATH}"
)

print("DATABASE:")
print(DATABASE_PATH)

print("\nTABLES:")

inspector = inspect(engine)

tables = inspector.get_table_names()

for table in tables:
    print("-", table)


print("\nTEST QUERY:")

with engine.connect() as connection:

    result = connection.execute(
        text('SELECT SUM("Sales") FROM "Sample - Superstore"')
    )

    total_sales = result.scalar()

    print("Total Sales:", total_sales)
    