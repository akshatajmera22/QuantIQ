import json


with open("metadata.json", "r", encoding="utf-8") as file:
    metadata = json.load(file)


for dataset_name, dataset in metadata.items():

    print("\n" + "=" * 60)
    print("DATASET:", dataset_name)
    print("=" * 60)

    print("Rows:", dataset["rows"])
    print("Columns:", len(dataset["columns"]))

    print("\nCOLUMN ANALYSIS:")

    for column_name, info in dataset["columns"].items():

        print(f"\n{column_name}")
        print(f"  Type: {info['type']}")
        print(f"  Data type: {info['dtype']}")
        print(f"  Unique values: {info['unique_values']}")
        print(f"  Null values: {info['null_values']}")
        print(f"  Unique ratio: {info['unique_ratio']}")
        print(
            f"  Possible identifier: "
            f"{info['possible_identifier']}"
        )
        print(
            f"  Samples: "
            f"{info['sample_values']}"
        )

        if info["type"] == "numeric":

            print(f"  Min: {info['min']}")
            print(f"  Max: {info['max']}")
            print(f"  Mean: {info['mean']}")