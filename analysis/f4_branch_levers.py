"""F4: Sizing and context for the CEO decisions, plus branch-mix and opening-hour levers.

Outputs (outputs/):
  f4_value_context.csv      chain GP, cost-gap values in % of chain/Garden GP, flat vs June run-rate (estimates)
  f4_cost_benchmark.csv     every branch's cost bill re-priced at the cheapest branch's unit costs
  f4_price_harmonisation.csv  Garden/Uptown prices raised to Harbour's, elasticity sweep (estimates)
  f4_tuesday_composition.csv  is Tuesday different customers/products, or just more traffic?
  f4_daily_volume_by_weekday.csv
  f4_opening_hours.csv      gross profit per opening hour per branch + break-even hourly cost
  f4_branch_mix_index.csv   category share per branch vs chain mean, by month (stability)
  f4_product_mix_index.csv
"""
import numpy as np
import pandas as pd

from common import BRANCHES, OUT, load_clean

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def unit_table(df):
    return df.groupby(["product", "branch"])[["price", "unit_cost"]].first().unstack("branch")


def value_context(df):
    u = unit_table(df)
    g = df[df.branch == "Garden"]
    excess_h = (g.cogs - g.qty * g["product"].map(u[("unit_cost", "Harbour")])).sum()
    excess_u = (g.cogs - g.qty * g["product"].map(u[("unit_cost", "Uptown")])).sum()
    chain_gp, garden_gp = df.gross_profit.sum(), g.gross_profit.sum()
    # Run-rate: June Garden COGS vs H1 monthly average
    m = g.assign(m=g.date.dt.to_period("M")).groupby("m").cogs.sum()
    june_factor = m.iloc[-1] / m.mean()
    rows = [
        ("chain_gross_profit_6m (measured)", chain_gp),
        ("garden_gross_profit_6m (measured)", garden_gp),
        ("garden_excess_cost_vs_harbour_6m (measured)", excess_h),
        ("garden_excess_cost_vs_uptown_6m (measured)", excess_u),
        ("excess_vs_harbour_as_pct_chain_gp", excess_h / chain_gp),
        ("excess_vs_harbour_as_pct_garden_gp", excess_h / garden_gp),
        ("garden_june_cogs_vs_h1_monthly_avg", june_factor),
        ("annual_value_flat_2xH1 (estimate)", 2 * excess_h),
        ("annual_value_june_run_rate (estimate)", 12 * excess_h / 6 * june_factor),
    ]
    # Single benchmark used in the README: every branch re-priced at Uptown's (cheapest) unit costs
    up = df["product"].map(u[("unit_cost", "Uptown")]) * df.qty
    exc = (df.cogs - up).groupby(df.branch).sum()
    exc_june = (df.cogs - up)[df.date.dt.month == 6].groupby(df.branch[df.date.dt.month == 6]).sum()
    total6, june = exc["Garden"] + exc["Harbour"], exc_june["Garden"] + exc_june["Harbour"]
    rows += [
        ("UPTOWN_BASIS garden_excess_6m (measured)", exc["Garden"]),
        ("UPTOWN_BASIS harbour_excess_6m (measured)", exc["Harbour"]),
        ("UPTOWN_BASIS total_excess_6m (measured)", total6),
        ("UPTOWN_BASIS total_excess_june (measured)", june),
        ("UPTOWN_BASIS total_as_pct_chain_gp", total6 / chain_gp),
        ("UPTOWN_BASIS garden_as_pct_garden_gp", exc["Garden"] / garden_gp),
        ("UPTOWN_BASIS annual_flat_2xH1 (estimate)", 2 * total6),
        ("UPTOWN_BASIS annual_june_run_rate_12xJune (estimate)", 12 * june),
    ]
    for b in ["Garden", "Harbour"]:
        rows += [(f"UPTOWN_BASIS {b.lower()}_annual_flat (estimate)", 2 * exc[b]),
                 (f"UPTOWN_BASIS {b.lower()}_annual_june_run_rate (estimate)", 12 * exc_june[b])]
    return pd.DataFrame(rows, columns=["item", "value"]).round(4)


def edge_hour_illustration(df, hourly_costs=(4, 6, 8, 10)):
    """ILLUSTRATIVE: yearly gross profit kept by closing 07:00 / 23:00 where the hour's GP < an ASSUMED hourly
    labour+energy cost. Ignores any knock-on loss of customers who come at those hours (assumption)."""
    days = df.date.nunique()
    gp = df[df.hour.isin([7, 23])].groupby(["branch", "hour"]).gross_profit.sum() / days
    rows = []
    for c in hourly_costs:
        loss = (c - gp).clip(lower=0)
        rows.append({"assumed_cost_per_open_hour_usd": c, "hours_losing_money": ", ".join(f"{b} {h}:00" for (b, h), v in loss.items() if v > 0) or "none",
                     "annual_saving_if_closed_usd (estimate)": round(loss.sum() * 365, 0)})
    return pd.DataFrame(rows)


def cost_benchmark(df):
    """Re-price every branch's units at each reference branch's unit cost."""
    u = unit_table(df)
    rows = []
    for b in BRANCHES:
        s = df[df.branch == b]
        for ref in BRANCHES:
            alt = (s.qty * s["product"].map(u[("unit_cost", ref)])).sum()
            rows.append({"branch": b, "reference_cost_base": ref, "actual_cogs_6m": s.cogs.sum(),
                         "cogs_at_reference_6m": alt, "saving_6m": s.cogs.sum() - alt})
    out = pd.DataFrame(rows)
    ratios = pd.DataFrame({f"{b}_cost_vs_Uptown": u[("unit_cost", b)] / u[("unit_cost", "Uptown")] for b in BRANCHES})
    out.attrs["ratio_summary"] = ratios.describe().loc[["min", "mean", "max"]]
    return out.round(2), ratios.describe().loc[["min", "mean", "max"]].round(4)


def price_harmonisation(df):
    """Raise a branch's prices to Harbour's. Constant-elasticity demand; elasticity is an ASSUMPTION."""
    u = unit_table(df)
    rows = []
    for b in ["Garden", "Uptown"]:
        s = df[df.branch == b]
        rev_h = (s.qty * s["product"].map(u[("price", "Harbour")]) * (1 - s.discount)).sum()
        uplift = rev_h / s.revenue.sum() - 1
        for e in [0.0, -0.5, -1.0, -1.5, -2.0]:
            vol = (1 + uplift) ** e
            rows.append({"branch": b, "price_uplift": uplift, "elasticity (assumption)": e,
                         "delta_gp_6m (estimate)": rev_h * vol - s.cogs.sum() * vol - s.gross_profit.sum()})
    return pd.DataFrame(rows).round(4)


def tuesday_composition(df):
    t = df.assign(is_tue=np.where(df.weekday == "Tue", "Tuesday", "Other days"))
    tx = t.groupby(["is_tue", "txn"]).agg(rev=("revenue", "sum"), n_items=("qty", "sum")).reset_index()
    rows = []
    for k, s in t.groupby("is_tue"):
        tk = tx[tx.is_tue == k]
        rows.append({"segment": k, "avg_order_value": tk.rev.mean(), "items_per_txn": tk.n_items.mean(),
                     "discounted_line_share": (s.discount > 0).mean(), "known_customer_line_share": s.customer.notna().mean(),
                     "takeaway_line_share": (s.order_type == "Takeaway").mean(),
                     "share_lines_19_22h": s.hour.between(19, 22).mean()})
    comp = pd.DataFrame(rows).set_index("segment").T
    cat = t.groupby(["is_tue", "category"]).size().unstack(0)
    cat = (cat / cat.sum()).add_prefix("category_share_")
    max_cat_gap = (cat.iloc[:, 0] - cat.iloc[:, 1]).abs().max()
    comp.loc["max_abs_category_share_gap"] = [max_cat_gap, max_cat_gap]
    return comp.round(4), cat.round(4)


def daily_by_weekday(df):
    d = df.groupby(["date", "weekday"]).txn.nunique().reset_index()
    out = d.groupby("weekday").txn.mean().loc[DAYS].rename("avg_txns_per_day_chain").to_frame()
    others = out.drop(index=["Tue", "Sat"]).avg_txns_per_day_chain.mean()
    out["vs_mean_of_mon_wed_thu_fri_sun"] = out.avg_txns_per_day_chain / others - 1
    return out.round(4)


def opening_hours(df):
    days = df.date.nunique()
    g = df.groupby(["branch", "hour"]).agg(gp=("gross_profit", "sum"), txns=("txn", "nunique"))
    g["gp_per_day"] = g.gp / days
    g["txns_per_day"] = g.txns / days
    out = g[["gp_per_day", "txns_per_day"]].unstack("branch")
    edge = out.loc[[7, 8, 22, 23]]
    return out.round(2), edge.round(2)


def mix_index(df):
    """Category line share per branch relative to the chain-wide share; computed per month to show stability."""
    df = df.assign(m=df.date.dt.strftime("%Y-%m"))
    share = df.groupby(["m", "branch", "category"]).size() / df.groupby(["m", "branch"]).size()
    chain = df.groupby(["m", "category"]).size() / df.groupby("m").size()
    idx = (share / chain).rename("index_vs_chain").reset_index()
    summ = idx.groupby(["branch", "category"]).index_vs_chain.agg(["mean", "min", "max"]).round(3)
    overall = (df.groupby(["branch", "category"]).size() / df.groupby("branch").size()).rename("line_share").round(4)
    summ = summ.join(overall)
    prod_share = df.groupby(["branch", "product"]).size() / df.groupby("branch").size()
    prod_mean = prod_share.groupby("product").mean()
    pidx = (prod_share / prod_share.index.get_level_values("product").map(prod_mean).to_numpy()).rename("index_vs_branch_mean").round(3)
    return summ, pidx.reset_index().sort_values("index_vs_branch_mean", ascending=False)


def main():
    df = load_clean()
    vc = value_context(df); vc.to_csv(OUT / "f4_value_context.csv", index=False)
    cb, rs = cost_benchmark(df); cb.to_csv(OUT / "f4_cost_benchmark.csv", index=False); rs.to_csv(OUT / "f4_cost_ratio_vs_uptown.csv")
    ph = price_harmonisation(df); ph.to_csv(OUT / "f4_price_harmonisation.csv", index=False)
    tc, tcat = tuesday_composition(df); tc.to_csv(OUT / "f4_tuesday_composition.csv"); tcat.to_csv(OUT / "f4_tuesday_category_mix.csv")
    dw = daily_by_weekday(df); dw.to_csv(OUT / "f4_daily_volume_by_weekday.csv")
    oh, edge = opening_hours(df); oh.to_csv(OUT / "f4_opening_hours.csv")
    eh = edge_hour_illustration(df); eh.to_csv(OUT / "f4_edge_hour_illustration.csv", index=False)
    print("--- edge-hour illustration\n" + eh.to_string(index=False))
    mi, pi = mix_index(df); mi.to_csv(OUT / "f4_branch_mix_index.csv"); pi.to_csv(OUT / "f4_product_mix_index.csv", index=False)

    pd.set_option("display.width", 220)
    for name, x in [("value context", vc), ("cost benchmark", cb), ("ratios vs Uptown", rs), ("price harmonisation", ph),
                    ("tuesday composition", tc), ("daily by weekday", dw), ("opening-hour edges (gp/day, txns/day)", edge)]:
        print(f"--- {name}\n{x.to_string()}")
    print("--- mix index (Desserts, Sandwiches)\n", mi.loc[(slice(None), ["Desserts", "Sandwiches"]), :])
    print("--- top product indices\n", pi.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
