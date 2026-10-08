import pandas as pd

df = pd.read_csv(
    "data/Sample - Superstore.csv",
    encoding="latin1"
)

print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\nTotal Sales:")
print(df["Sales"].sum())

print("\nTotal Profit:")
print(df["Profit"].sum())

print("\nSales by Region:")
print(
    df.groupby("Region")["Sales"]
    .sum()
    .sort_values(ascending=False)
)

print("\nTop 5 Products by Profit:")
print(
    df.groupby("Product Name")["Profit"]
    .sum()
    .sort_values(ascending=False)
    .head(5)
)