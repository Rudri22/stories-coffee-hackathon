"""F3: Hourly demand forecast per branch for staffing and baking. Is a model better than a simple baseline?

Train: 2026-01-01 .. 2026-05-31.  Holdout (never used for fitting): 2026-06-01 .. 2026-06-30.
Target: transactions per branch per hour (07:00-23:00).
Baseline: seasonal naive = mean of the last 4 same-weekday, same-hour values in the training window.
Model: Poisson GLM, log(mu) = branch*hour + branch*weekday + branch*trend.
Staffing translation uses ASSUMPTION A7 (transactions one staff member can serve per hour), swept 10..20.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import OneHotEncoder

from common import BRANCHES, OUT, load_clean

SPLIT = pd.Timestamp("2026-06-01")
HOURS = range(7, 24)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def hourly_panel(df):
    tx = df.drop_duplicates("txn")
    counts = tx.groupby(["branch", "date", "hour"]).size()
    idx = pd.MultiIndex.from_product([BRANCHES, pd.date_range(df.date.min(), df.date.max()), HOURS], names=["branch", "date", "hour"])
    p = counts.reindex(idx, fill_value=0).rename("y").reset_index()
    p["weekday"] = p.date.dt.day_name().str[:3]
    p["t"] = (p.date - p.date.min()).dt.days / 30.0
    return p


def seasonal_naive(train, test):
    last4 = (train.sort_values("date").groupby(["branch", "weekday", "hour"]).tail(4)
             .groupby(["branch", "weekday", "hour"]).y.mean().rename("pred"))
    return test.join(last4, on=["branch", "weekday", "hour"])["pred"].to_numpy()


def design(p, enc=None):
    cat = pd.DataFrame({"bh": p.branch + "_" + p.hour.astype(str), "bw": p.branch + "_" + p.weekday})
    if enc is None:
        enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore").fit(cat)
    X = enc.transform(cat)
    trend = np.column_stack([(p.branch == b).to_numpy() * p.t.to_numpy() for b in BRANCHES])
    return np.hstack([X, trend]), enc


def glm(train, test):
    Xtr, enc = design(train)
    m = PoissonRegressor(alpha=1e-4, max_iter=3000).fit(Xtr, train.y)
    return m.predict(design(test, enc)[0])


def metrics(name, y, pred, level):
    err = pred - y
    return {"model": name, "level": level, "WAPE": np.abs(err).sum() / y.sum(), "MAE": np.abs(err).mean(),
            "bias_pct": err.sum() / y.sum()}


def staffing(test, pred_col, cap):
    """Staff per hour = ceil(forecast/cap), min 1. Under = hours where actual demand needed more staff."""
    need = np.maximum(1, np.ceil(test.y / cap))
    plan = np.maximum(1, np.ceil(test[pred_col] / cap))
    return {"short_staffed_hours": int((plan < need).sum()), "excess_staff_hours": int(np.clip(plan - need, 0, None).sum()),
            "missing_staff_hours": int(np.clip(need - plan, 0, None).sum())}


def weekday_effect(p):
    """Alternative-explanation check: is 'Tuesday ~1.6x' a stable weekly pattern or driven by a few outlier days?"""
    d = p.groupby(["date", "weekday"]).y.sum().reset_index()
    d["week"] = d.date.dt.isocalendar().week
    wk = d.pivot_table(index="week", columns="weekday", values="y").dropna()[DAYS]
    ratio = wk["Tue"] / wk.drop(columns="Tue").mean(axis=1)
    return wk, ratio


def main():
    df = load_clean()
    p = hourly_panel(df)
    train, test = p[p.date < SPLIT].copy(), p[p.date >= SPLIT].copy()
    test["baseline"] = seasonal_naive(train, test)
    test["model"] = glm(train, test)

    rows = []
    for col in ["baseline", "model"]:
        rows.append(metrics(col, test.y.to_numpy(), test[col].to_numpy(), "branch-hour"))
        d = test.groupby(["branch", "date"])[["y", col]].sum()
        rows.append(metrics(col, d.y.to_numpy(), d[col].to_numpy(), "branch-day"))
        tue = test[test.weekday == "Tue"]
        rows.append(metrics(col, tue.y.to_numpy(), tue[col].to_numpy(), "branch-hour, Tuesdays"))
        pk = test[test.hour.between(19, 22)]
        rows.append(metrics(col, pk.y.to_numpy(), pk[col].to_numpy(), "branch-hour, 19-22h peak"))
    met = pd.DataFrame(rows).round(4)
    met.to_csv(OUT / "f3_holdout_metrics.csv", index=False)

    st = []
    for cap in [10, 15, 20]:
        for col in ["baseline", "model"]:
            st.append({"txns_per_staff_hour (ASSUMPTION)": cap, "plan": col, **staffing(test, col, cap)})
    st = pd.DataFrame(st)
    st.to_csv(OUT / "f3_staffing_holdout.csv", index=False)

    wk, ratio = weekday_effect(p)
    wk.to_csv(OUT / "f3_weekly_by_weekday.csv")
    prof = p.groupby(["weekday", "hour"]).y.mean().unstack("hour").loc[DAYS].round(2)
    prof.to_csv(OUT / "f3_avg_txns_weekday_hour_all_branches.csv")
    monthly = p.assign(m=p.date.dt.strftime("%Y-%m")).groupby(["m", "branch"]).y.sum().unstack()[BRANCHES]
    monthly.to_csv(OUT / "f3_monthly_transactions.csv")
    test.to_csv(OUT / "f3_holdout_predictions.csv", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    d = test.groupby("date")[["y", "baseline", "model"]].sum()
    ax[0].plot(d.index, d.y, "k-", label="actual"); ax[0].plot(d.index, d.baseline, "--", label="seasonal-naive baseline"); ax[0].plot(d.index, d.model, label="Poisson model")
    ax[0].set_title("June 2026 holdout: daily transactions, all branches"); ax[0].legend(fontsize=8); ax[0].tick_params(axis="x", rotation=45)
    im = ax[1].imshow(prof.to_numpy(), aspect="auto", cmap="viridis")
    ax[1].set_yticks(range(7), DAYS); ax[1].set_xticks(range(len(prof.columns)), prof.columns); ax[1].set_xlabel("hour")
    ax[1].set_title("Avg transactions per branch-hour"); fig.colorbar(im, ax=ax[1])
    fig.tight_layout(); fig.savefig(OUT / "f3_forecast_and_heatmap.png", dpi=130); plt.close(fig)

    pd.set_option("display.width", 200)
    print(met.to_string(index=False)); print(st.to_string(index=False))
    print("Tuesday / other-weekday-mean ratio per week: min %.2f median %.2f max %.2f (n=%d weeks)" % (ratio.min(), ratio.median(), ratio.max(), len(ratio)))
    print(monthly)


if __name__ == "__main__":
    main()
