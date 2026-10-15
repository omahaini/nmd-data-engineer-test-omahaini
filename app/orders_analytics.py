"""Analytics helpers for the orders pipeline.

All functions take a pandas DataFrame of orders (one row per order line) and
return a new DataFrame, so they can be tested without touching AWS.

Assumptions (also documented in the top-level readme.md):
  * The input has no profit column, so profit is derived per row as
        (List Price * (1 - Discount Percent / 100) - cost price) * Quantity
  * "Number of orders" means DISTINCT Order Ids.
  * "Not Available" in Ship Mode is a placeholder for a missing value and is
    ignored when finding the most common ship method (a Category whose orders
    are ALL "Not Available" therefore does not appear in that report).
  * Rows whose price/cost/quantity/discount cannot be parsed as numbers get no
    profit; they are excluded from the profit total and a warning is logged.
  * Ties are broken alphabetically so results are deterministic.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Order Id",
    "Ship Mode",
    "Region",
    "Category",
    "Sub Category",
    "cost price",
    "List Price",
    "Quantity",
    "Discount Percent",
]
NUMERIC_COLUMNS = ["cost price", "List Price", "Quantity", "Discount Percent"]
PLACEHOLDER_SHIP_MODES = {"Not Available"}


def validate_orders(orders_df):
    "Raise a clear error if any column needed by the reports is missing"
    missing = [col for col in REQUIRED_COLUMNS if col not in orders_df.columns]
    if missing:
        raise ValueError(f"Input file is missing required columns: {missing}")
    if orders_df.empty:
        raise ValueError("Input file contains no orders")


def calculate_profit_by_order(orders_df):
    "Calculate profit for each order in the DataFrame"
    df = orders_df.copy()
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    sale_price = df["List Price"] * (1 - df["Discount Percent"] / 100)
    df["Profit"] = (sale_price - df["cost price"]) * df["Quantity"]

    unparseable = int(df["Profit"].isna().sum())
    if unparseable:
        logger.warning("%d row(s) have non-numeric values and are excluded from profit", unparseable)
    return df


def calculate_most_profitable_region(orders_df):
    "Calculate the most profitable region and its profit"
    df = calculate_profit_by_order(orders_df)
    totals = df.groupby("Region")["Profit"].sum()
    if totals.empty:
        raise ValueError("No orders to analyse")

    best_region = totals.idxmax()  # first (alphabetical) region wins a tie
    return pd.DataFrame(
        {"Region": [best_region], "Total Profit": [round(float(totals[best_region]), 2)]}
    )


def find_most_common_ship_method(orders_df):
    "Find the most common shipping method for each Category"
    df = orders_df[~orders_df["Ship Mode"].isin(PLACEHOLDER_SHIP_MODES)]
    counts = (
        df.groupby(["Category", "Ship Mode"])["Order Id"]
        .nunique()
        .reset_index(name="Order Count")
    )
    # Highest count first; alphabetical Ship Mode breaks ties.
    counts = counts.sort_values(
        ["Category", "Order Count", "Ship Mode"], ascending=[True, False, True]
    )
    top = counts.drop_duplicates(subset="Category", keep="first")
    return top.rename(columns={"Ship Mode": "Most Common Ship Mode"}).reset_index(drop=True)


def find_number_of_order_per_category(orders_df):
    "find the number of orders for each Category and Sub Category"
    return (
        orders_df.groupby(["Category", "Sub Category"])["Order Id"]
        .nunique()
        .reset_index(name="Order Count")
    )


def run_all_reports(orders_df):
    "Validate the input and return {report_name: DataFrame} for every report"
    validate_orders(orders_df)
    return {
        "most_profitable_region": calculate_most_profitable_region(orders_df),
        "most_common_ship_method_by_category": find_most_common_ship_method(orders_df),
        "order_count_by_category_subcategory": find_number_of_order_per_category(orders_df),
    }
