"""F1: Why does Garden earn ~18 points less gross margin than Harbour, and what is it worth?

Outputs (outputs/):
  f1_branch_pnl.csv            measured 6-month P&L by branch
  f1_unit_ratios.csv           per-product Garden/Uptown price and cost relative to Harbour
  f1_margin_bridge.csv         Harbour margin -> Garden margin split into mix / price / cost
  f1_ratio_stability.csv       cost ratio by month, category, order type (alternative explanations)
  f1_value_scenarios.csv       ESTIMATED gross-profit impact of actions (assumption-driven)
  f1_garden_product_margins.csv
  f1_*.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import BRANCHES, OUT, load_clean, load_raw


def branch_pnl(df):
    g = df.groupby("branch").agg(lines=("txn", "size"), transactions=("txn", "nunique"),
                                 revenue=("revenue", "sum"), cogs=("cogs", "sum"),
                                 gross_profit=("gross_profit", "sum"))
    g["gross_margin"] = g["gross_profit"] / g["revenue"]
    g["avg_order_value"] = g["revenue"] / g["transactions"]
    g["discounted_line_share"] = df.groupby("branch")["discount"].apply(lambda s: (s > 0).mean())
    return g.loc[BRANCHES].round(4)


def unit_ratios(df):
    p = df.groupby(["product", "category", "branch"])[["price", "unit_cost"]].first().unstack("branch")
    out = pd.DataFrame(index=p.index)
    for b in ["Garden", "Uptown"]:
        out[f"{b}_price_vs_Harbour"] = p[("price", b)] / p[("price", "Harbour")]
        out[f"{b}_cost_vs_Harbour"] = p[("unit_cost", b)] / p[("unit_cost", "Harbour")]
    for b in BRANCHES:
        out[f"{b}_unit_margin"] = 1 - p[("unit_cost", b)] / p[("price", b)]
    return out.round(4).reset_index()


def margin_bridge(df):
    """Sequential decomposition on Garden's actual basket (qty, discounts) of the gap to Harbour's margin."""
    ref = df[df.branch == "Harbour"].groupby("product")[["price", "unit_cost"]].first()
    g = df[df.branch == "Garden"].join(ref, on="product", rsuffix="_h")
    h = df[df.branch == "Harbour"]
    m = lambda rev, cost: 1 - cost.sum() / rev.sum()
    rev_h_prices = g.qty * g.price_h * (1 - g.discount)
    steps = [
        ("Harbour actual margin", m(h.revenue, h.cogs)),
        ("Garden basket at Harbour prices & costs (mix + discount effect)", m(rev_h_prices, g.qty * g.unit_cost_h)),
        ("+ Garden prices, Harbour costs (price effect)", m(g.revenue, g.qty * g.unit_cost_h)),
        ("+ Garden costs = Garden actual margin (cost effect)", m(g.revenue, g.cogs)),
    ]
    b = pd.DataFrame(steps, columns=["step", "gross_margin"])
    b["change_pts"] = (b["gross_margin"].diff() * 100).round(2)
    b["gross_margin"] = b["gross_margin"].round(4)
    return b


def ratio_stability(df):
    """If the cost gap came from waste, theft, a supplier price change or mix, the ratio would vary
    by month/category/channel. It is tested here (alternative explanations, R03/R04)."""
    ref = df[df.branch == "Harbour"].groupby("product")["unit_cost"].first()
    g = df[df.branch == "Garden"].copy()
    g["harbour_cost"] = g["product"].map(ref) * g["qty"]
    rows = []
    for dim in ["month", "category", "order_type"]:
        key = g["date"].dt.strftime("%Y-%m") if dim == "month" else g[dim]
        s = g.groupby(key).agg(garden_cogs=("cogs", "sum"), cogs_at_harbour_cost=("harbour_cost", "sum"))
        for k, r in s.iterrows():
            rows.append({"dimension": dim, "value": k, "garden_cost_over_harbour": round(r.garden_cogs / r.cogs_at_harbour_cost, 4)})
    return pd.DataFrame(rows)


def value_scenarios(df):
    """ESTIMATES. Base = measured H1-2026 Garden volumes. Annualised = x2 (ASSUMPTION A6: flat volume, which is conservative
    given the +49% Jan->Jun growth)."""
    ref = df.groupby(["product", "branch"])[["price", "unit_cost"]].first()
    g = df[df.branch == "Garden"].copy()
    hc = g["product"].map(ref.xs("Harbour", level="branch")["unit_cost"]) * g.qty
    uc = g["product"].map(ref.xs("Uptown", level="branch")["unit_cost"]) * g.qty
    gp, cogs, rev = g.gross_profit.sum(), g.cogs.sum(), g.revenue.sum()
    rows = [
        ("A. Garden unit costs brought to Harbour level", cogs - hc.sum()),
        ("B. Close half of the cost gap", (cogs - hc.sum()) / 2),
        ("C. Garden unit costs brought to Uptown level", cogs - uc.sum()),
    ]
    # D: price alignment to Harbour (+5.0%) under constant-elasticity demand, elasticity is an ASSUMPTION
    hp = g["product"].map(ref.xs("Harbour", level="branch")["price"])
    rev_h = (g.qty * hp * (1 - g.discount)).sum()
    uplift = rev_h / rev - 1
    for e in [0.0, -0.5, -1.0, -1.5, -2.0]:
        vol = (1 + uplift) ** e
        rows.append((f"D. Garden prices raised to Harbour (+{uplift:.1%}), elasticity {e}", rev_h * vol - cogs * vol - gp))
    out = pd.DataFrame(rows, columns=["scenario", "delta_gross_profit_6m_usd"])
    out["delta_gross_profit_annualised_usd"] = out["delta_gross_profit_6m_usd"] * 2
    out["garden_gp_6m_measured_usd"] = gp
    return out.round(0)


def garden_products(df):
    g = df[df.branch == "Garden"].groupby(["product", "category"]).agg(units=("qty", "sum"), revenue=("revenue", "sum"), gross_profit=("gross_profit", "sum"))
    g["gross_margin"] = g.gross_profit / g.revenue
    return g.sort_values("gross_margin").round(4).reset_index()


def category_mix(df):
    """Share of lines and gross margin per category and branch (does Garden lean on low-margin categories?)."""
    g = df.groupby(["category", "branch"]).agg(lines=("txn", "size"), revenue=("revenue", "sum"), gp=("gross_profit", "sum"))
    g["line_share"] = g.lines / g.groupby("branch").lines.transform("sum")
    g["gross_margin"] = g.gp / g.revenue
    return g[["line_share", "gross_margin"]].unstack("branch").round(4)


def shared_customers(df):
    c = df.dropna(subset=["customer"]).groupby("customer").branch.nunique()
    return pd.DataFrame({"known_customers": [len(c)], "share_visiting_2plus_branches": [round((c >= 2).mean(), 4)]})


def plots(pnl, ratios, bridge):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].bar(pnl.index, pnl.gross_margin * 100, color=["#4C72B0", "#C44E52", "#55A868"])
    for i, v in enumerate(pnl.gross_margin * 100):
        ax[0].text(i, v + 1, f"{v:.1f}%", ha="center")
    ax[0].set_ylabel("Gross margin (%)"); ax[0].set_title("Gross margin by branch, Jan–Jun 2026"); ax[0].set_ylim(0, 75)
    x = np.arange(len(ratios))
    ax[1].scatter(x, ratios.Garden_cost_vs_Harbour, label="Garden unit cost / Harbour", color="#C44E52", s=14)
    ax[1].scatter(x, ratios.Garden_price_vs_Harbour, label="Garden price / Harbour", color="#4C72B0", s=14)
    ax[1].scatter(x, ratios.Uptown_cost_vs_Harbour, label="Uptown unit cost / Harbour", color="#55A868", s=14)
    ax[1].axhline(1, color="grey", lw=0.8); ax[1].set_xticks([]); ax[1].set_xlabel("45 products")
    ax[1].set_title("Same ratio on every product"); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "f1_margin_and_ratios.png", dpi=130); plt.close(fig)

    # One chart that shows "formula, not waste": each product's Garden/Harbour unit-cost ratio on a flat line
    r = ratios.sort_values(["category", "product"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.scatter(r.index, r.Garden_cost_vs_Harbour, color="#C44E52", s=22, zorder=3)
    ax.axhline(1.43, color="grey", lw=1, ls="--"); ax.text(len(r) - 0.5, 1.4335, "1.43", ha="right", va="bottom", color="grey")
    ax.set_ylim(1.0, 1.6); ax.set_ylabel("Garden unit cost / Harbour unit cost")
    ax.set_xticks(r.index, r["product"], rotation=90, fontsize=7)
    ax.set_title("Garden's unit cost is 1.43x Harbour's on every product: perishable food, drinks, bakery alike")
    fig.tight_layout(); fig.savefig(OUT / "f1_cost_ratio_by_product.png", dpi=130); plt.close(fig)


def main():
    df = load_clean(verbose=True)
    pnl = branch_pnl(df); pnl.to_csv(OUT / "f1_branch_pnl.csv")
    pnl_raw = branch_pnl(load_raw())
    ratios = unit_ratios(df); ratios.to_csv(OUT / "f1_unit_ratios.csv", index=False)
    bridge = margin_bridge(df); bridge.to_csv(OUT / "f1_margin_bridge.csv", index=False)
    stab = ratio_stability(df); stab.to_csv(OUT / "f1_ratio_stability.csv", index=False)
    val = value_scenarios(df); val.to_csv(OUT / "f1_value_scenarios.csv", index=False)
    gp = garden_products(df); gp.to_csv(OUT / "f1_garden_product_margins.csv", index=False)
    cm = category_mix(df); cm.to_csv(OUT / "f1_category_mix_and_margin.csv")
    sc = shared_customers(df); sc.to_csv(OUT / "f1_shared_customers.csv", index=False)
    plots(pnl, ratios, bridge)

    pd.set_option("display.width", 200)
    print(pnl); print("margin incl. duplicates:", pnl_raw.gross_margin.round(4).to_dict())
    print(ratios.filter(like="vs_Harbour").describe().loc[["min", "mean", "max", "std"]].round(4))
    print(bridge.to_string(index=False))
    print(stab.groupby("dimension").garden_cost_over_harbour.agg(["min", "max"]))
    print(val[["scenario", "delta_gross_profit_6m_usd", "delta_gross_profit_annualised_usd"]].to_string(index=False))
    print(gp.head(8).to_string(index=False))
    print(cm.loc[["Desserts", "Sandwiches"]]); print(sc.to_string(index=False))


if __name__ == "__main__":
    main()
