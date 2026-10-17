"""F5: The branch formula decoded, what the promotion reveals about price sensitivity, and the demand calendar.

Outputs (outputs/):
  f5_branch_rules.csv          price and unit-cost lists: master branch, multiplier per branch, exact cent matches
  f5_price_endings.csv         share of each branch's 45 prices ending in 5 cents (hand-set vs computed)
  f5_price_sensitivity.csv     promo-implied price elasticity: point, robustness range, plausible bound
  f5_pricing_scenarios.csv     ESTIMATED gross profit from raising Garden/Uptown prices to Harbour's at those elasticities
  f5_daypart_mix.csv           takeaway and category share by time of day
  f5_holiday_effects.csv       Lebanese public holidays 2026: traffic vs matched weekdays, all branches and per branch
  f5_holiday_test.csv          how many holidays fall outside the range of ordinary days (binomial check)
  f5_ramadan_profile.csv       hourly shape of demand before / during / after Ramadan 2026
  f5_seasonality.csv           cold vs hot drink share by month
  f5_background_discount.csv   who gets the 10% discount (targeting check)

decode_branch_rules() is generic: it works on any multi-branch export with product, branch, price, unit_cost columns.
"""
import numpy as np
import pandas as pd
from scipy.stats import binom

from common import BRANCHES, HOLIDAYS_2026, OUT, load_clean

PROMO_RATE = 0.15
GRID = np.round(np.arange(0.5, 2.0 + 1e-9, 0.0001), 4)
RAMADAN = ("2026-02-18", "2026-03-19")


def round_cents(x):
    """Round half up to the cent, robust to float error."""
    return np.floor(np.asarray(x) * 100 + 0.5 + 1e-9) / 100


def best_factor(src, dst):
    """Multiplier f maximising exact cent matches dst == round(src * f); prefers the 'cleanest' f (fewest decimals)."""
    pred = round_cents(np.outer(GRID, src))
    matches = (np.abs(pred - np.asarray(dst)) < 1e-6).sum(axis=1)
    cands = GRID[matches == matches.max()]
    for dec in (2, 3, 4):
        clean = cands[np.isclose(cands, np.round(cands, dec))]
        if len(clean):
            return float(clean[np.argmin(np.abs(clean - np.median(cands)))]), int(matches.max())
    return float(cands[0]), int(matches.max())


def decode_branch_rules(df, fields=("price", "unit_cost")):
    """For each field, find a reference branch whose list reproduces the other branches' lists via one multiplier each.
    Rounding to the cent makes the mapping reversible (the inverse multiplier reproduces the reference list too), so the
    multipliers alone cannot say which list is the original; reverse_direction_matches reports that check."""
    rows = []
    for field in fields:
        t = df.groupby(["product", "branch"])[field].first().unstack("branch").dropna()
        branches = list(t.columns)
        best = None
        for anchor in branches:
            fits = [(b, *best_factor(t[anchor].to_numpy(), t[b].to_numpy())) for b in branches if b != anchor]
            total = sum(m for _, _, m in fits)
            if best is None or total > best[0]:
                best = (total, anchor, fits)
        _, anchor, fits = best
        rows.append({"field": field, "branch": anchor, "rule": "reference list", "multiplier": 1.0,
                     "exact_cent_matches": len(t), "reverse_direction_matches": np.nan, "n_products": len(t)})
        for b, f, m in fits:
            rev = int((np.abs(round_cents(t[b].to_numpy() / f) - t[anchor].to_numpy()) < 1e-6).sum())
            rows.append({"field": field, "branch": b, "rule": f"{anchor} x {f}", "multiplier": f,
                         "exact_cent_matches": m, "reverse_direction_matches": rev, "n_products": len(t)})
    return pd.DataFrame(rows)


def equal_cost_ranking(df):
    """Gross margin per branch as reported vs with every branch on Uptown's (cheapest) unit costs, plus how alike the
    branches behave (order value, takeaway share, food attach), to show whether rankings reflect operations or costing."""
    cu = df[df.branch == "Uptown"].groupby("product").unit_cost.first()
    tx = df.groupby(["branch", "txn"]).agg(rev=("revenue", "sum"), cats=("category", lambda c: set(c))).reset_index()
    drinks = {"Hot Coffee", "Cold Coffee", "Matcha & Tea", "Cold Drinks"}
    rows = []
    for b in BRANCHES:
        s = df[df.branch == b]
        t = tx[tx.branch == b]
        dr = t[t.cats.apply(lambda c: bool(c & drinks))]
        rows.append({"branch": b, "margin_reported": s.gross_profit.sum() / s.revenue.sum(),
                     "margin_at_uptown_unit_costs": 1 - (s.qty * s["product"].map(cu)).sum() / s.revenue.sum(),
                     "avg_order_value": t.rev.mean(), "takeaway_share": (s.order_type == "Takeaway").mean(),
                     "food_attach_on_drink_orders": dr.cats.apply(lambda c: bool(c - drinks)).mean()})
    out = pd.DataFrame(rows)
    out["rank_reported"] = out.margin_reported.rank(ascending=False).astype(int)
    out["rank_at_equal_costs"] = out.margin_at_uptown_unit_costs.rank(ascending=False).astype(int)
    return out.round(4)


def price_endings(df):
    p = df.groupby(["product", "branch"]).price.first().unstack("branch")
    last = (p * 100).round().astype(int) % 10
    return pd.DataFrame({"share_of_prices_ending_in_5_cents": (last == 5).mean(), "n_products": len(p)}).round(4)


def price_sensitivity():
    """Constant-elasticity reading of the Harbour promotion: Q ~ P^e, so e = ln(1 + lift) / ln(1 - 0.15)."""
    did = pd.read_csv(OUT / "f2_did_results.csv").set_index("segment_metric").loc["promoted units"]
    rob = pd.read_csv(OUT / "f2_robustness.csv")
    e = lambda lift: np.log(1 + lift) / np.log(1 - PROMO_RATE)
    lift = did["did"]
    # Test inversion: lifts consistent with the observed DiD given the campaign-shaped placebo spread
    lift_hi = lift - did["block_placebo_did_p2.5"]
    lift_lo = lift - did["block_placebo_did_p97.5"]
    rows = [
        ("measured unit lift (DiD)", lift, e(lift)),
        ("robustness: smallest lift", rob.promoted_units_did.min(), e(rob.promoted_units_did.min())),
        ("robustness: largest lift", rob.promoted_units_did.max(), e(rob.promoted_units_did.max())),
        ("plausible upper lift (test inversion, ~95%)", lift_hi, e(lift_hi)),
        ("plausible lower lift (test inversion, ~95%)", lift_lo, e(lift_lo)),
    ]
    return pd.DataFrame(rows, columns=["reading", "unit_lift", "implied_elasticity"]).round(4)


def pricing_scenarios(df, sens):
    """Raise a branch's prices to Harbour's. Elasticities come from the promotion, not from an assumption sweep."""
    u = df.groupby(["product", "branch"]).price.first().unstack("branch")
    point = sens.set_index("reading").implied_elasticity
    cases = [("point estimate", point["measured unit lift (DiD)"]),
             ("most price-sensitive robustness spec", point["robustness: largest lift"]),
             ("plausible bound (most price-sensitive)", point["plausible upper lift (test inversion, ~95%)"]),
             ("stress: elasticity -2.0 (not measured)", -2.0)]
    rows = []
    for b in ["Garden", "Uptown"]:
        s = df[df.branch == b]
        rev_h = (s.qty * s["product"].map(u["Harbour"]) * (1 - s.discount)).sum()
        uplift = rev_h / s.revenue.sum() - 1
        margin = s.gross_profit.sum() / s.revenue.sum()
        breakeven_drop = 1 - margin / (margin + uplift)  # unit drop that leaves gross profit unchanged
        # Decisions 1 and 2 interact: if unit costs fell to Uptown's level, margin rises and the break-even drop shrinks
        cu = df[df.branch == "Uptown"].groupby("product").unit_cost.first()
        m_fixed = 1 - (s.qty * s["product"].map(cu)).sum() / s.revenue.sum()
        breakeven_fixed = 1 - m_fixed / (m_fixed + uplift)
        for name, e in cases:
            vol = (1 + uplift) ** e
            d6 = rev_h * vol - s.cogs.sum() * vol - s.gross_profit.sum()
            rows.append({"branch": b, "price_uplift": uplift, "case": name, "elasticity": e,
                         "delta_gp_6m (estimate)": d6, "delta_gp_annual_flat (estimate)": 2 * d6,
                         "breakeven_unit_drop": breakeven_drop, "breakeven_unit_drop_if_costs_at_uptown_level": breakeven_fixed})
    out = pd.DataFrame(rows)
    tot = out.groupby("case", sort=False)[["delta_gp_6m (estimate)", "delta_gp_annual_flat (estimate)"]].sum().reset_index()
    tot.insert(0, "branch", "Garden+Uptown")
    return pd.concat([out, tot], ignore_index=True).round(4)


def pilot_products(df, n=5):
    """Selection rule, fixed before any threshold: Uptown's top n products by units sold, Jan-Jun."""
    return list(df[df.branch == "Uptown"].groupby("product").qty.sum().sort_values(ascending=False).head(n).index)


def pilot_thresholds(df):
    """Per-product break-even unit drop for raising Garden/Uptown prices to Harbour's: d = 1 - m / (m + u), with m the
    product's full-price unit margin at that branch and u its price rise. A branch-wide average can approve a product
    that loses money, so the pilot uses each selected product's own threshold."""
    pilot = pilot_products(df)
    t = df[df.discount == 0].groupby(["product", "branch"])[["price", "unit_cost"]].first().unstack("branch")
    rows = []
    for b in ["Garden", "Uptown"]:
        m = 1 - t[("unit_cost", b)] / t[("price", b)]
        up = t[("price", "Harbour")] / t[("price", b)] - 1
        be = 1 - m / (m + up)
        for prod in t.index:
            rows.append({"branch": b, "product": prod, "price_rise": up[prod], "unit_margin": m[prod],
                         "breakeven_unit_drop": be[prod], "in_pilot": prod in pilot})
    return pd.DataFrame(rows).round(4)


def pilot_power(df, threshold=-0.12, true_drop=-0.25):
    """How noisy is the pilot's statistic with NO price change? Statistic = (Uptown units, test / baseline window) /
    (Garden+Harbour units, test / baseline) - 1, over consecutive L-week windows in the full weeks 5 Jan - 28 Jun.
    false_stop = P(statistic < threshold | no change); false_approve = P(a true -25% drop still passes the threshold)."""
    d = df[(df.date >= "2026-01-05") & (df.date <= "2026-06-28")].copy()
    d["week"] = (d.date - pd.Timestamp("2026-01-05")).dt.days // 7
    d["grp"] = np.where(d.branch == "Uptown", "U", "C")
    w = d.groupby(["product", "grp", "week"]).qty.sum().unstack("week", fill_value=0)
    n_weeks = w.shape[1]

    def stats(products, L):
        u, c = w.xs("U", level="grp").loc[products].sum(), w.xs("C", level="grp").loc[products].sum()
        out = []
        for i in range(0, n_weeks - 2 * L + 1):
            ub, ut = u.iloc[i:i + L].sum(), u.iloc[i + L:i + 2 * L].sum()
            cb, ct = c.iloc[i:i + L].sum(), c.iloc[i + L:i + 2 * L].sum()
            out.append((ut / ub) / (ct / cb) - 1)
        return np.array(out)

    pilot = pilot_products(df)
    menu = list(w.index.get_level_values("product").unique())
    rows = []

    def add(design, x, units_per_window):
        rows.append({"design": design, "windows": len(x), "uptown_units_per_window": units_per_window, "sd": x.std(ddof=1),
                     "false_stop_no_change": (x < threshold).mean(),
                     "false_approve_true_minus25pct": ((1 + true_drop) * (1 + x) - 1 >= threshold).mean()})

    per = {p: stats([p], 4) for p in pilot}
    for p, x in per.items():
        add(f"per product, 4 weeks: {p}", x, w.xs("U", level="grp").loc[p].sum() / n_weeks * 4)
    allx = np.vstack(list(per.values()))
    rows.append({"design": "at least one of the 5 products wrongly stopped, 4 weeks", "windows": allx.shape[1],
                 "false_stop_no_change": (allx < threshold).any(axis=0).mean()})
    up = w.xs("U", level="grp")
    add("5 products pooled, 4 weeks", stats(pilot, 4), up.loc[pilot].sum().sum() / n_weeks * 4)
    add("5 products pooled, 8 weeks", stats(pilot, 8), up.loc[pilot].sum().sum() / n_weeks * 8)
    add("whole Uptown menu, 4 weeks", stats(menu, 4), up.sum().sum() / n_weeks * 4)
    menu8 = stats(menu, 8)
    add("whole Uptown menu, 8 weeks", menu8, up.sum().sum() / n_weeks * 8)
    out = pd.DataFrame(rows)
    i = out.index[out.design == "whole Uptown menu, 8 weeks"][0]
    out.loc[i, ["min", "max", "mean"]] = [menu8.min(), menu8.max(), menu8.mean()]

    # Decision rule "go only if Uptown's gross profit relative to the controls does not fall", evaluated on the GROSS-PROFIT
    # metric itself: past 8-week windows are repriced line by line at Harbour's prices, with a uniform unit response r.
    hp = df[df.branch == "Harbour"].groupby("product").price.first()
    du = d[d.branch == "Uptown"]
    rep0 = (du.qty * (du["product"].map(hp) * (1 - du.discount) - du.unit_cost)).groupby(du.week).sum()  # repriced GP, r = 0
    gu = du.gross_profit.groupby(du.week).sum()
    gc = d[d.branch != "Uptown"].gross_profit.groupby(d[d.branch != "Uptown"].week).sum()
    L = 8
    win = range(0, n_weeks - 2 * L + 1)
    ctrl = np.array([gc.iloc[i + L:i + 2 * L].sum() / gc.iloc[i:i + L].sum() for i in win])
    base = np.array([gu.iloc[i:i + L].sum() for i in win])
    hist = np.array([gu.iloc[i + L:i + 2 * L].sum() for i in win]) / base / ctrl - 1
    test0 = np.array([rep0.iloc[i + L:i + 2 * L].sum() for i in win])
    r_be = gu.sum() / rep0.sum() - 1  # unit response at which the price rise leaves gross profit unchanged
    rule = [{"scenario": "no price change (historical drift of the metric)", "true_unit_response": np.nan, "true_gp_change": 0.0,
             "share_negative_8wk": (hist < 0).mean(), "metric_min": hist.min(), "metric_max": hist.max(), "metric_mean": hist.mean(),
             "windows": len(hist)}]
    for name, r in [("price rise, no reaction", 0.0), ("units -5%", -0.05), ("units -8%", -0.08), ("units -10%", -0.10),
                    ("units just past break-even", round(r_be - 0.001, 4)), ("units -16%", -0.16)]:
        sim = (1 + r) * test0 / base / ctrl - 1
        rule.append({"scenario": name, "true_unit_response": r, "true_gp_change": (1 + r) * rep0.sum() / gu.sum() - 1,
                     "share_negative_8wk": (sim < 0).mean(), "metric_min": sim.min(), "metric_max": sim.max(),
                     "metric_mean": sim.mean(), "windows": len(sim)})
    rule = pd.DataFrame(rule)
    rule["breakeven_unit_response"] = r_be
    return out.round(4), rule.round(4)


def daypart_mix(df):
    band = pd.cut(df.hour, [6, 10, 14, 18, 24], labels=["07-10", "11-14", "15-18", "19-23"])
    cat = df.groupby([band, "category"], observed=True).size().unstack()
    out = cat.div(cat.sum(axis=1), axis=0)
    out.insert(0, "takeaway_share", df.groupby(band, observed=True).order_type.apply(lambda s: (s == "Takeaway").mean()))
    out.insert(1, "share_of_all_lines", df.groupby(band, observed=True).size() / len(df))
    tue = df[(df.weekday == "Tue") & df.hour.between(20, 22) & (df.branch == "Harbour")]
    out.loc["Harbour Tue 20-23h", "takeaway_share"] = (tue.order_type == "Takeaway").mean()
    return out.round(4)


def matched_ratio(series, day, excluded):
    ctrl = [day + pd.Timedelta(weeks=k) for k in (-3, -2, -1, 1, 2, 3)]
    ctrl = [c for c in ctrl if c in series.index and c not in excluded]
    return series[day] / series[ctrl].mean() if len(ctrl) >= 3 else np.nan


def holiday_effects(df):
    """A holiday 'stands out' if chain traffic falls outside the range of 95% of ordinary days AND all three branches
    move in that direction. The same rule is applied to ordinary days to get the chance rate for the binomial check."""
    tx = df.drop_duplicates("txn")
    allb = tx.groupby("date").size()
    perb = tx.groupby(["branch", "date"]).size()
    hol = {pd.Timestamp(d): n for d, n in HOLIDAYS_2026}
    excluded = set(hol)

    def day_row(d):
        r = {"ratio_all_branches": matched_ratio(allb, d, excluded)}
        for b in BRANCHES:
            r[f"ratio_{b}"] = matched_ratio(perb.loc[b], d, excluded)
        return r

    ordinary = pd.DataFrame([dict(date=d, **day_row(d)) for d in allb.index if d not in excluded]).dropna()
    lo, hi = np.percentile(ordinary.ratio_all_branches, [2.5, 97.5])

    def stands_out(r):
        outside = not (lo <= r["ratio_all_branches"] <= hi)
        same_dir = all(np.sign(r[f"ratio_{b}"] - 1) == np.sign(r["ratio_all_branches"] - 1) for b in BRANCHES)
        return outside, outside and same_dir

    flags = ordinary.apply(lambda r: stands_out(r)[1], axis=1)
    p0 = flags.mean()
    rows = []
    for d, name in hol.items():
        r = {"date": d.date(), "weekday": d.day_name()[:3], "holiday": name, **day_row(d)}
        r["outside_ordinary_95pct_range"], r["stands_out_at_all_three_branches"] = stands_out(r)
        rows.append(r)
    eff = pd.DataFrame(rows).round(3)
    k, n = int(eff.stands_out_at_all_three_branches.sum()), len(eff)
    test = pd.DataFrame([{"ordinary_day_ratio_p2.5": lo, "ordinary_day_ratio_p97.5": hi, "n_ordinary_days": len(ordinary),
                          "chance_rate_ordinary_days_stand_out": p0, "holidays_tested": n,
                          "holidays_outside_range_any_direction": int(eff.outside_ordinary_95pct_range.sum()),
                          "holidays_standing_out_all_branches": k, "expected_by_chance": p0 * n,
                          "binomial_p_at_least_k": binom.sf(k - 1, n, p0)}]).round(4)
    return eff, test


def month_cycle(df):
    """Start-of-month lift: each day's transactions vs the same weekday 1-3 weeks either side. Strict version keeps only
    days with all six matched days present (two-sided window) and excludes public holidays on both sides."""
    t = df.drop_duplicates("txn")
    hol = {pd.Timestamp(d) for d, _ in HOLIDAYS_2026}

    def ratios(day):
        out = {}
        for d in day.index:
            c = [d + pd.Timedelta(weeks=k) for k in (-3, -2, -1, 1, 2, 3)]
            c = [x for x in c if x in day.index and x not in hol]
            if len(c) == 6 and d not in hol:
                out[d] = day[d] / day[c].mean()
        return pd.Series(out)

    def first5_vs_rest(r):
        f, o = r[r.index.day <= 5], r[r.index.day > 5]
        return f.mean() - o.mean(), (f.mean() - o.mean()) / np.sqrt(f.var() / len(f) + o.var() / len(o)), len(f)

    allr = ratios(t.groupby("date").size())
    diff, z, n = first5_vs_rest(allr)
    rows = [{"segment": "all branches", "days_1_5_minus_rest": diff, "z": z, "n_days_1_5": n, "n_days": len(allr)}]
    for b in BRANCHES:
        d_, z_, n_ = first5_vs_rest(ratios(t[t.branch == b].groupby("date").size()))
        rows.append({"segment": f"branch {b}", "days_1_5_minus_rest": d_, "z": z_, "n_days_1_5": n_})
    for mo, g in allr.groupby(allr.index.month):
        if (g.index.day <= 5).any():
            f, o = g[g.index.day <= 5], g[g.index.day > 5]
            rows.append({"segment": f"month {mo}", "days_1_5_minus_rest": f.mean() - o.mean(), "n_days_1_5": len(f)})
    k = df.groupby("txn").agg(d=("date", "first"), rev=("revenue", "sum"))
    rows.append({"segment": "avg order value days 1-5", "days_1_5_minus_rest": k[k.d.dt.day <= 5].rev.mean()})
    rows.append({"segment": "avg order value days 6-31", "days_1_5_minus_rest": k[k.d.dt.day > 5].rev.mean()})
    by_day = allr.groupby(allr.index.day).mean().rename("mean_ratio_vs_matched_weekdays")
    return pd.DataFrame(rows).round(4), by_day.round(4)


def ramadan_profile(df):
    tx = df.drop_duplicates("txn")
    win = {"4 weeks before": ("2026-01-21", "2026-02-17"), "Ramadan": RAMADAN, "4 weeks after": ("2026-03-21", "2026-04-17")}
    cols = {}
    for k, (a, b) in win.items():
        w = tx[(tx.date >= a) & (tx.date <= b)]
        cols[k] = w.groupby("hour").size() / len(w)
        cols[k]["txns_per_day"] = len(w) / w.date.nunique()
    out = pd.DataFrame(cols)
    shares = out.drop(index="txns_per_day")
    out.loc["max_abs_hour_share_gap_vs_before_after_avg_pts"] = [
        np.nan, (shares["Ramadan"] - (shares["4 weeks before"] + shares["4 weeks after"]) / 2).abs().max() * 100, np.nan]
    return out.round(4)


def seasonality(df):
    m = df.assign(month=df.date.dt.strftime("%Y-%m")).groupby("month")
    return pd.DataFrame({"cold_drink_share (Cold Coffee + Cold Drinks)": m.category.apply(lambda s: s.isin(["Cold Coffee", "Cold Drinks"]).mean()),
                         "hot_coffee_share": m.category.apply(lambda s: (s == "Hot Coffee").mean())}).round(4)


def background_discount(df):
    d = df.discount == 0.10
    band = pd.cut(df.hour, [6, 10, 14, 18, 24], labels=["07-10", "11-14", "15-18", "19-23"])
    rows = [("known customer", d[df.customer.notna()].mean()), ("anonymous", d[df.customer.isna()].mean())]
    rows += [(f"branch {b}", d[df.branch == b].mean()) for b in BRANCHES]
    rows += [(f"daypart {k}", v) for k, v in d.groupby(band, observed=True).mean().items()]
    by_cat = d.groupby(df.category).mean()
    rows += [("category min", by_cat.min()), ("category max", by_cat.max())]
    rows += [("discount given, 6 months (USD)", (df.qty * df.price - df.revenue)[d].sum())]
    return pd.DataFrame(rows, columns=["segment", "share_of_lines_with_10pct_discount"]).round(4)


def main():
    df = load_clean()
    rules = decode_branch_rules(df); rules.to_csv(OUT / "f5_branch_rules.csv", index=False)
    ends = price_endings(df); ends.to_csv(OUT / "f5_price_endings.csv")
    rank = equal_cost_ranking(df); rank.to_csv(OUT / "f5_equal_cost_ranking.csv", index=False)
    print("--- equal-cost ranking\n" + rank.to_string(index=False))
    sens = price_sensitivity(); sens.to_csv(OUT / "f5_price_sensitivity.csv", index=False)
    scen = pricing_scenarios(df, sens); scen.to_csv(OUT / "f5_pricing_scenarios.csv", index=False)
    pil = pilot_thresholds(df); pil.to_csv(OUT / "f5_pilot_thresholds.csv", index=False)
    pw, rule = pilot_power(df); pw.to_csv(OUT / "f5_pilot_power.csv", index=False)
    rule.to_csv(OUT / "f5_pilot_decision_rule.csv", index=False)
    print("--- pilot power\n" + pw.to_string(index=False))
    print("--- pilot thresholds (range by branch, then pilot products at Uptown)")
    print(pil.groupby("branch").breakeven_unit_drop.agg(["min", "max"]).to_string())
    print(pil[(pil.branch == "Uptown") & pil.in_pilot][["product", "unit_margin", "breakeven_unit_drop"]].to_string(index=False))
    dp = daypart_mix(df); dp.to_csv(OUT / "f5_daypart_mix.csv")
    hol, test = holiday_effects(df); hol.to_csv(OUT / "f5_holiday_effects.csv", index=False); test.to_csv(OUT / "f5_holiday_test.csv", index=False)
    ram = ramadan_profile(df); ram.to_csv(OUT / "f5_ramadan_profile.csv")
    mc, mcd = month_cycle(df); mc.to_csv(OUT / "f5_month_cycle.csv", index=False); mcd.to_csv(OUT / "f5_month_cycle_by_day.csv")
    sea = seasonality(df); sea.to_csv(OUT / "f5_seasonality.csv")
    bg = background_discount(df); bg.to_csv(OUT / "f5_background_discount.csv", index=False)

    pd.set_option("display.width", 220)
    for name, x in [("branch rules", rules), ("price endings", ends), ("price sensitivity", sens), ("pricing scenarios", scen),
                    ("daypart (takeaway + share)", dp[["takeaway_share", "share_of_all_lines"]]), ("holidays", hol), ("holiday test", test),
                    ("ramadan", ram.loc[["txns_per_day", "max_abs_hour_share_gap_vs_before_after_avg_pts"]]), ("seasonality", sea),
                    ("background discount", bg)]:
        print(f"--- {name}\n{x.to_string()}")


if __name__ == "__main__":
    main()
