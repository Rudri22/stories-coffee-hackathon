"""F2: Did discount campaigns pay for themselves?

Campaign days are detected from the data (daily discounted-line share > median + 3*MAD), not assumed.
Lift = campaign-day transactions vs the same branch & weekday in the 3 weeks before and after (non-campaign days).
This is an observational comparison (R10): it is not a controlled experiment.
"""
import numpy as np
import pandas as pd

from common import BRANCHES, OUT, load_clean


def main():
    df = load_clean()
    df["discounted"] = df.discount > 0
    day = df.groupby("date").agg(lines=("txn", "size"), disc_lines=("discounted", "sum"))
    day["disc_share"] = day.disc_lines / day.lines
    med = day.disc_share.median(); mad = (day.disc_share - med).abs().median()
    day["campaign"] = day.disc_share > med + 3 * 1.4826 * mad
    camp_days = day.index[day.campaign]
    day.to_csv(OUT / "f2_daily_discount_share.csv")

    tx = df.groupby(["branch", "date"]).agg(txns=("txn", "nunique"), revenue=("revenue", "sum"), gp=("gross_profit", "sum"),
                                           discount_usd=("discount", lambda s: 0)).reset_index()
    disc_usd = (df.qty * df.price - df.revenue).groupby([df.branch, df.date]).sum()
    tx["discount_usd"] = tx.set_index(["branch", "date"]).index.map(disc_usd).fillna(0)
    tx = tx.set_index(["branch", "date"])

    rows = []
    for b in BRANCHES:
        for d in camp_days:
            ctrl = [d + pd.Timedelta(weeks=k) for k in (-3, -2, -1, 1, 2, 3)]
            ctrl = [c for c in ctrl if (b, c) in tx.index and c not in camp_days]
            if len(ctrl) < 3:
                continue
            c = tx.loc[[(b, x) for x in ctrl]]
            r = tx.loc[(b, d)]
            rows.append({"branch": b, "date": d.date(), "weekday": d.day_name()[:3], "n_control_days": len(ctrl),
                         "txns": r.txns, "control_txns_mean": c.txns.mean(), "txn_lift_pct": r.txns / c.txns.mean() - 1,
                         "gp": r.gp, "control_gp_mean": c.gp.mean(), "gp_lift_usd": r.gp - c.gp.mean(), "discount_usd": r.discount_usd})
    ev = pd.DataFrame(rows)
    ev.to_csv(OUT / "f2_campaign_event_study.csv", index=False)

    # Placebo: same method on random non-campaign days, to see what "lift" looks like by chance
    rng = np.random.default_rng(0)
    non = [d for d in day.index if d not in camp_days]
    plac = []
    for _ in range(300):
        d = non[rng.integers(len(non))]; b = BRANCHES[rng.integers(3)]
        ctrl = [d + pd.Timedelta(weeks=k) for k in (-3, -2, -1, 1, 2, 3)]
        ctrl = [c for c in ctrl if (b, c) in tx.index and c not in camp_days]
        if len(ctrl) >= 3:
            plac.append(tx.loc[(b, d)].txns / tx.loc[[(b, x) for x in ctrl]].txns.mean() - 1)
    plac = np.array(plac)
    # Null distribution of the MEAN lift over len(ev) branch-days: resample placebo lifts
    null_means = np.array([rng.choice(plac, size=len(ev)).mean() for _ in range(5000)])

    # Basket comparison (correlational)
    t = df.groupby("txn").agg(items=("qty", "sum"), aov=("revenue", "sum"), has_disc=("discounted", "any"), branch=("branch", "first"))
    basket = t.groupby("has_disc")[["items", "aov"]].mean()
    basket.to_csv(OUT / "f2_basket_discount_vs_not.csv")
    rate = df[df.discounted].groupby(["branch", "discount"]).size().unstack(fill_value=0)
    rate.to_csv(OUT / "f2_discount_rate_by_branch.csv")

    s = ev.agg({"txn_lift_pct": "mean", "gp_lift_usd": "sum", "discount_usd": "sum"})
    pd.DataFrame([{"campaign_days": ", ".join(str(d.date()) for d in camp_days), "branch_days": len(ev),
                   "mean_txn_lift_pct": s.txn_lift_pct, "share_branch_days_with_positive_lift": (ev.txn_lift_pct > 0).mean(),
                   "total_gp_lift_vs_control_usd": s.gp_lift_usd, "total_discount_given_on_campaign_days_usd": s.discount_usd,
                   "placebo_mean_lift_pct": plac.mean(),
                   "share_null_means_at_or_below_observed": (null_means <= s.txn_lift_pct).mean(),
                   "share_null_means_at_or_above_observed": (null_means >= s.txn_lift_pct).mean(), "placebo_p5_pct": np.percentile(plac, 5), "placebo_p95_pct": np.percentile(plac, 95),
                   "total_discount_all_period_usd": (df.qty * df.price - df.revenue).sum()}]).round(4).T.to_csv(OUT / "f2_summary.csv", header=["value"])

    pd.set_option("display.width", 200)
    print("campaign days:", [str(d.date()) for d in camp_days], "median share %.3f" % med)
    print(day.loc[camp_days, "disc_share"].round(3).to_dict())
    print(ev.round(3).to_string(index=False))
    print("mean lift %.3f, positive share %.2f, GP lift sum %.0f, discount sum %.0f" % (s.txn_lift_pct, (ev.txn_lift_pct > 0).mean(), s.gp_lift_usd, s.discount_usd))
    print("placebo lift mean %.3f p5 %.3f p95 %.3f" % (plac.mean(), np.percentile(plac, 5), np.percentile(plac, 95)))
    print("null mean-lift: share <= observed %.3f, share >= observed %.3f" % ((null_means <= s.txn_lift_pct).mean(), (null_means >= s.txn_lift_pct).mean()))
    print(basket.round(3)); print(rate)


if __name__ == "__main__":
    main()
