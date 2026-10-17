"""Evidence for approaches we considered and rejected (R12): each would need a real difference to act on."""
import pandas as pd

from common import BRANCHES, OUT, load_clean

DRINKS = {"Hot Coffee", "Cold Coffee", "Matcha & Tea", "Cold Drinks"}


def main():
    df = load_clean()
    rows = []
    # 1. Cross-sell / basket attach: does any branch under-sell food with drinks?
    cats = df.groupby(["branch", "txn"]).category.agg(set)
    for b in BRANCHES:
        s = cats.loc[b]; d = s[s.apply(lambda c: bool(c & DRINKS))]
        rows.append(("food attach rate on drink orders", b, round(d.apply(lambda c: bool(c - DRINKS)).mean(), 4)))
    # 2. Customer churn / retention: is there a churn problem to model?
    known = df.dropna(subset=["customer"])
    visits = known.groupby("customer").txn.nunique()
    first = known.groupby("customer").date.min()
    rows.append(("known customers", "all", len(visits)))
    rows.append(("share of known customers with 2+ visits", "all", round((visits >= 2).mean(), 4)))
    rows.append(("share of known customers first seen in Jan-Feb", "all", round((first < "2026-03-01").mean(), 4)))
    # 3. Order channel: does takeaway vs dine-in differ in value?
    t = df.groupby(["txn", "order_type"]).revenue.sum().reset_index()
    for k, v in t.groupby("order_type").revenue.mean().items():
        rows.append(("avg order value", k, round(v, 2)))
    # 4. Loyalty vs anonymous basket
    t = df.assign(known=df.customer.notna()).groupby(["txn", "known"]).revenue.sum().reset_index()
    for k, v in t.groupby("known").revenue.mean().items():
        rows.append(("avg order value", "known customer" if k else "anonymous", round(v, 2)))
    out = pd.DataFrame(rows, columns=["check", "segment", "value"])
    out.to_csv(OUT / "rejected_checks.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
