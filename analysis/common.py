"""Shared loading and cleaning. Every cleaning step is logged so it can be audited."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

BRANCHES = ["Harbour", "Garden", "Uptown"]


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(DATA, dtype={"Customer ID": "string"})
    df = df.rename(columns={
        "Transaction ID": "txn", "Date": "date", "Time": "time", "Branch": "branch",
        "Customer ID": "customer", "Order Type": "order_type", "Product": "product",
        "Category": "category", "Quantity": "qty", "Unit Price (USD)": "price",
        "Discount Rate": "discount", "Unit Cost (USD)": "unit_cost",
        "Line Revenue (USD)": "revenue", "Line Gross Profit (USD)": "gross_profit",
    })
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"])
    df["date"] = pd.to_datetime(df["date"])
    df["hour"] = df["ts"].dt.hour
    df["weekday"] = df["ts"].dt.day_name().str[:3]
    df["cogs"] = df["qty"] * df["unit_cost"]
    return df


def load_clean(verbose: bool = False) -> pd.DataFrame:
    """Drop exact duplicate lines (ASSUMPTION A2: identical lines = double logging)."""
    raw = load_raw()
    clean = raw.drop_duplicates(subset=[c for c in raw.columns if c not in ("ts", "hour", "weekday", "cogs")])
    if verbose:
        print(f"raw lines={len(raw)}  exact duplicates removed={len(raw) - len(clean)}  clean lines={len(clean)}")
    return clean.reset_index(drop=True)


def data_quality_report() -> pd.DataFrame:
    raw = load_raw()
    dup = raw.duplicated(subset=[c for c in raw.columns if c not in ("ts", "hour", "weekday", "cogs")])
    checks = {
        "lines": len(raw),
        "transactions": raw["txn"].nunique(),
        "days": raw["date"].nunique(),
        "first_date": raw["date"].min().date().isoformat(),
        "last_date": raw["date"].max().date().isoformat(),
        "exact_duplicate_lines": int(dup.sum()),
        "duplicate_revenue_usd": round(raw.loc[dup, "revenue"].sum(), 2),
        "revenue_formula_mismatches": int(((raw["qty"] * raw["price"] * (1 - raw["discount"]) - raw["revenue"]).abs() > 0.011).sum()),
        "gross_profit_formula_mismatches": int(((raw["revenue"] - raw["cogs"] - raw["gross_profit"]).abs() > 0.011).sum()),
        "blank_customer_id_share": round(raw["customer"].isna().mean(), 4),
        "txns_with_conflicting_header_fields": int((raw.groupby("txn")[["date", "time", "branch", "customer", "order_type"]].nunique(dropna=False) > 1).any(axis=1).sum()),
        "product_branch_pairs_with_more_than_one_price": int((raw.groupby(["product", "branch"])["price"].nunique() > 1).sum()),
        "product_branch_pairs_with_more_than_one_unit_cost": int((raw.groupby(["product", "branch"])["unit_cost"].nunique() > 1).sum()),
        "negative_values": int((raw[["qty", "price", "unit_cost", "revenue", "gross_profit"]] < 0).sum().sum()),
    }
    return pd.DataFrame(list(checks.items()), columns=["check", "value"])
