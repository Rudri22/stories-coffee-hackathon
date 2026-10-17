"""Optional stress tests of the headline claims (not part of run_all.py; ~3 min). Run after run_all.py:
    python analysis/stress_tests.py

Outputs (outputs/):
  stress_ranking.csv        branch ranking on margin, gross profit per order and total gross profit,
                            as reported and on Uptown's / Harbour's unit costs
  stress_definitions.csv    branch margins net of discounts vs on list price, duplicates removed vs kept
  stress_placebo_seeds.csv  campaign-shaped placebo range for promoted units under 5 random seeds
"""
import numpy as np
import pandas as pd

import f2_promotions as f2
from common import BRANCHES, OUT, load_clean, load_raw


def ranking(df):
    u = df.groupby(["product", "branch"]).unit_cost.first().unstack()
    rows = []
    for b in BRANCHES:
        s = df[df.branch == b]
        n = s.txn.nunique()
        r = {"branch": b, "margin_reported": s.gross_profit.sum() / s.revenue.sum(),
             "gp_per_order_reported": s.gross_profit.sum() / n, "total_gp_reported": s.gross_profit.sum()}
        for base in ["Uptown", "Harbour"]:
            cogs = (s.qty * s["product"].map(u[base])).sum()
            r[f"margin_at_{base}_costs"] = 1 - cogs / s.revenue.sum()
            r[f"gp_per_order_at_{base}_costs"] = (s.revenue.sum() - cogs) / n
        rows.append(r)
    t = pd.DataFrame(rows).set_index("branch")
    ranks = t.rank(ascending=False).astype(int).add_prefix("rank_")
    return t.round(4).join(ranks)


def definitions(df, raw):
    rows = []
    for name, d in [("duplicates removed", df), ("duplicates kept", raw)]:
        for b in BRANCHES:
            s = d[d.branch == b]
            rows.append({"data": name, "branch": b, "margin_net_of_discounts": s.gross_profit.sum() / s.revenue.sum(),
                         "margin_on_list_price": 1 - s.cogs.sum() / (s.qty * s.price).sum()})
    return pd.DataFrame(rows).round(4)


def placebo_seeds(df, seeds=(0, 1, 2, 3, 4), n=1000):
    promo = df[df.discount == f2.PROMO_RATE]
    days = sorted(promo.date.unique())
    d, t = f2.daily(df, sorted(promo.category.unique()))
    excluded = set(days)
    all_days = d.loc[("Harbour", "promoted")].index
    starts = [i for i in range(len(all_days) - 7) if all(all_days[i + k] not in excluded for k in range(8))]
    obs = f2.did(d, t, days, excluded, "units", "promoted").did.mean()
    h = df[(df.branch == "Harbour") & df.category.isin(promo.category.unique()) & (df.discount == 0)]
    m = h.gross_profit.sum() / h.revenue.sum()
    gap = f2.PROMO_RATE / (m - f2.PROMO_RATE) - obs  # how far the true lift would have to exceed the estimate to break even
    rows = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        pl = []
        while len(pl) < n:
            a, b = sorted(rng.choice(starts, size=2, replace=False))
            if b - a >= 8:
                pl.append(f2.did(d, t, [all_days[a + k] for k in range(8)] + [all_days[b + k] for k in range(8)],
                                 excluded, "units", "promoted").did.mean())
        pl = np.array(pl)
        rows.append({"seed": seed, "placebo_p2.5": np.percentile(pl, 2.5), "placebo_p97.5": np.percentile(pl, 97.5),
                     "placebo_p99": np.percentile(pl, 99), "gap_to_breakeven": gap, "share_placebos_reaching_gap": (pl >= gap).mean()})
    return pd.DataFrame(rows).round(4)


def main():
    df, raw = load_clean(), load_raw()
    r = ranking(df); r.to_csv(OUT / "stress_ranking.csv")
    dfn = definitions(df, raw); dfn.to_csv(OUT / "stress_definitions.csv", index=False)
    ps = placebo_seeds(df); ps.to_csv(OUT / "stress_placebo_seeds.csv", index=False)
    pd.set_option("display.width", 220)
    print(r.to_string()); print(dfn.to_string(index=False)); print(ps.to_string(index=False))


if __name__ == "__main__":
    main()
