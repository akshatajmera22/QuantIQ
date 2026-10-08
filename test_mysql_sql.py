from sql_generator import generate_sql


plan = {
    "analyses": [
        {
            "intent": "Find total payment amount",

            "table": "payment",

            "metric_column": "amount",

            "aggregation": "SUM",

            "calculation": {
                "type": "none",
                "numerator_column": "",
                "numerator_operator": "=",
                "numerator_value": "",
                "denominator": ""
            },

            "group_by": [],

            "filters": [],

            "sort_column": "",

            "sort_direction": "",

            "limit": 0,

            "date_column": ""
        }
    ]
}


queries = generate_sql(
    plan=plan,
    schema_context="",
    dialect="mysql"
)


print()
print("MYSQL SQL TEST")
print("=" * 50)

for item in queries:

    print()
    print(item["sql"])

print()
print("=" * 50)