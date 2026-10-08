from planner import create_query_plan
from sql_builder import build_sql
from agent import get_schema, get_database_values
import os


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE_PATH = os.path.join(
    BASE_DIR,
    "database.db"
)


questions = [
    "top 5 cars with most horsepower",
    "which car has the highest horsepower?",
    "cars with more than 400 horsepower",
    "how many silver Mercedes-Benz in IL",
    "electric green Audi Q7",
    "average selling price of Audi",
]


for question in questions:

    print()
    print("=" * 70)
    print("QUESTION:")
    print(question)

    try:

        schema = get_schema()

        values = get_database_values()

        plan = create_query_plan(
            question,
            schema,
            values
        )

        print()
        print("QUERY PLAN:")
        print(plan)

        sql = build_sql(
            plan,
            DATABASE_PATH
        )

        print()
        print("GENERATED SQL:")
        print(sql)

    except Exception as e:

        print()
        print("ERROR:")
        print(e)