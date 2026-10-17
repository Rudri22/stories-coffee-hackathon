"""Shared loading and cleaning. Every cleaning step is logged so it can be audited."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _find_data() -> Path:
    """data/stories_transactions.csv, else any stories*.csv in data/ or the repo root (e.g. 'stories_transactions (1).csv')."""
    preferred = ROOT / "data" / "stories_transactions.csv"
    if preferred.exists():
        return preferred
    for folder in (ROOT / "data", ROOT):
        found = sorted(folder.glob("stories*.csv")) or sorted(folder.glob("*transactions*.csv"))
        if found:
            return found[0]
    raise FileNotFoundError(
        "Transaction CSV not found. Place the provided file at data/stories_transactions.csv "
        f"(searched {ROOT / 'data'} and {ROOT} for stories*.csv / *transactions*.csv).")


DATA = _find_data()
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

BRANCHES = ["Harbour", "Garden", "Uptown"]

# Lebanese public holidays in the data window (published 2026 calendars). Islamic dates are provisional (moon sighting).
HOLIDAYS_2026 = [
    ("2026-01-01", "New Year's Day"), ("2026-01-06", "Armenian Christmas"), ("2026-02-09", "St Maroun's Day"),
    ("2026-03-20", "Eid al-Fitr day 1"), ("2026-03-21", "Eid al-Fitr day 2"), ("2026-03-22", "Eid al-Fitr day 3"),
    ("2026-03-23", "Eid al-Fitr day 4"), ("2026-03-25", "Annunciation"), ("2026-04-03", "Good Friday (Western)"),
    ("2026-04-05", "Easter Sunday (Western)"), ("2026-04-10", "Good Friday (Orthodox)"),
    ("2026-04-12", "Easter Sunday (Orthodox)"), ("2026-05-01", "Labour Day"),
    ("2026-05-25", "Resistance and Liberation Day"), ("2026-05-27", "Eid al-Adha"),
]


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
        "txns_with_same_product_on_two_lines": int((raw[~dup].groupby(["txn", "product"]).size() > 1).sum()),
        "of_which_with_different_discounts": int((raw[~dup].groupby(["txn", "product"]).discount.nunique() > 1).sum()),
        "share_consecutive_txn_ids_back_in_time": round(float(
            (raw.drop_duplicates("txn").assign(n=lambda d: d.txn.str[4:].astype(int)).sort_values("n").ts.diff().dt.total_seconds() < 0).mean()), 3),
    }
    return pd.DataFrame(list(checks.items()), columns=["check", "value"])
