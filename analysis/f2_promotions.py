"""F2: Did Harbour's 15% promotions pay for themselves?

Facts from the data (not assumed):
  * The 15% discount appears ONLY at Harbour, ONLY on 16 days (12-19 Mar, 12-19 May), and ONLY on Cold Coffee
    and Desserts. On those days every unit of those products was discounted.
  * Elsewhere, a 10% discount appears at a steady background rate at all branches.

Design: difference-in-differences on daily units and gross profit.
  treated  = Harbour x promoted categories on promo days
  baseline = the same branch x category on the same weekday 1-3 weeks before/after (non-promo days)
  control  = the same comparison for Garden+Uptown (same categories, same days) -> removes chain-wide day effects
Placebo: the same DiD on random non-promo days shows how large a DiD appears by chance.
Correlation caveat (R10): no randomisation; the promo dates may have been chosen for a reason.
"""
import numpy as np
import pandas as pd

from common import OUT, load_clean

PROMO_RATE = 0.15


def daily(df, promo_cats):
    df = df.assign(seg=np.where(df.category.isin(promo_cats), "promoted", "other"),
                   grp=np.where(df.branch == "Harbour", "Harbour", "Garden+Uptown"),
                   list_rev=df.qty * df.price)
    d = df.groupby(["grp", "seg", "date"]).agg(units=("qty", "sum"), gp=("gross_profit", "sum"),
                                               revenue=("revenue", "sum"), list_rev=("list_rev", "sum"))
    t = df.groupby(["grp", "date"]).txn.nunique().rename("txns")
    return d, t


def matched(series, day, excluded):
    ctrl = [day + pd.Timedelta(weeks=k) for k in (-3, -2, -1, 1, 2, 3)]
    ctrl = [c for c in ctrl if c in series.index and c not in excluded]
    return series.loc[ctrl].mean() if len(ctrl) >= 3 else np.nan


def did(d, t, days, excluded, metric, seg):
    """Mean over days of: (Harbour actual/matched - 1) - (Garden+Uptown actual/matched - 1)."""
    out = []
    for day in days:
        h = d.loc[("Harbour", seg)][metric] if metric != "txns" else t.loc["Harbour"]
        c = d.loc[("Garden+Uptown", seg)][metric] if metric != "txns" else t.loc["Garden+Uptown"]
        mh, mc = matched(h, day, excluded), matched(c, day, excluded)
        out.append({"date": day, "harbour_change": h.loc[day] / mh - 1, "control_change": c.loc[day] / mc - 1,
                    "harbour_actual": h.loc[day], "harbour_matched": mh})
    o = pd.DataFrame(out)
    o["did"] = o.harbour_change - o.control_change
    return o


def main():
    df = load_clean()
    promo = df[df.discount == PROMO_RATE]
    promo_days = sorted(promo.date.unique())
    promo_cats = sorted(promo.category.unique())
    facts = {
        "promo_days": len(promo_days),
        "promo_dates": f"{pd.Timestamp(promo_days[0]).date()}..{pd.Timestamp(promo_days[7]).date()} and {pd.Timestamp(promo_days[8]).date()}..{pd.Timestamp(promo_days[-1]).date()}",
        "promo_branches": ",".join(sorted(promo.branch.unique())),
        "promo_categories": ",".join(promo_cats),
        "promo_lines": len(promo),
        "harbour_promoted_lines_on_promo_days_sold_at_full_price": int(((df.branch == "Harbour") & df.date.isin(promo_days)
                                                                        & df.category.isin(promo_cats) & (df.discount == 0)).sum()),
        "discount_given_usd_15pct": round((promo.qty * promo.price - promo.revenue).sum(), 2),
        "discount_given_usd_all_rates_6m": round((df.qty * df.price - df.revenue).sum(), 2),
    }
    d, t = daily(df, promo_cats)
    excluded = set(promo_days)
    rng = np.random.default_rng(0)
    all_days = d.loc[("Harbour", "promoted")].index
    non = [x for x in all_days if x not in excluded]

    rows, details = [], []
    for seg, metric in [("promoted", "units"), ("promoted", "gp"), ("other", "units"), ("other", "gp"), (None, "txns")]:
        o = did(d, t, promo_days, excluded, metric, seg)
        plac = []
        for _ in range(1000):
            sample = list(rng.choice(non, size=len(promo_days), replace=False))
            plac.append(did(d, t, sample, excluded, metric, seg).did.mean())
        plac = np.array(plac)
        label = f"{seg or 'all'} {metric}"
        rows.append({"segment_metric": label, "harbour_change_vs_matched": o.harbour_change.mean(),
                     "control_change_vs_matched": o.control_change.mean(), "did": o.did.mean(),
                     "harbour_total_actual": o.harbour_actual.sum(), "harbour_total_matched": o.harbour_matched.sum(),
                     "placebo_did_p2.5": np.percentile(plac, 2.5), "placebo_did_p97.5": np.percentile(plac, 97.5),
                     "share_placebo_as_extreme": (np.abs(plac) >= abs(o.did.mean())).mean()})
        details.append(o.assign(segment_metric=label))
    res = pd.DataFrame(rows).round(4)
    res.to_csv(OUT / "f2_did_results.csv", index=False)
    pd.concat(details).round(4).to_csv(OUT / "f2_did_by_day.csv", index=False)

    # Break-even: units lift needed so that 15% off still earns the same gross profit on promoted items (Harbour)
    h = df[(df.branch == "Harbour") & df.category.isin(promo_cats) & (df.discount == 0)]
    unit_margin = (h.gross_profit.sum() / h.qty.sum()) / (h.revenue.sum() / h.qty.sum())
    breakeven = PROMO_RATE / (unit_margin - PROMO_RATE)
    facts.update({"harbour_promoted_full_price_margin": round(unit_margin, 4), "breakeven_unit_lift_for_15pct": round(breakeven, 4)})

    # Post-promo displacement: promoted units at Harbour in the 7 days after each block (DiD vs control)
    after = [pd.Timestamp(promo_days[7]) + pd.Timedelta(days=k) for k in range(1, 8)] + \
            [pd.Timestamp(promo_days[-1]) + pd.Timedelta(days=k) for k in range(1, 8)]
    after = [a for a in after if a in all_days]
    pa = did(d, t, after, excluded | set(after), "units", "promoted")
    facts.update({"post_promo_7d_promoted_units_did": round(pa.did.mean(), 4)})
    pd.DataFrame(list(facts.items()), columns=["fact", "value"]).to_csv(OUT / "f2_facts.csv", index=False)

    pd.set_option("display.width", 220)
    print(pd.DataFrame(list(facts.items()), columns=["fact", "value"]).to_string(index=False))
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
