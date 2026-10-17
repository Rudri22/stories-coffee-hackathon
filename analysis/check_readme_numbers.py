"""Consistency test: every headline number in README.md must match the generated outputs.
Run after run_all.py:  python analysis/check_readme_numbers.py   (exit code 1 on any mismatch)"""
import sys

import pandas as pd

from common import OUT, ROOT

sys.stdout.reconfigure(encoding="utf-8")  # README literals include −, ×, ≈ (Windows consoles default to cp1252)

readme = (ROOT / "README.md").read_text(encoding="utf-8")
f = lambda name: pd.read_csv(OUT / name)
vc = f("f4_value_context.csv").set_index("item").value
did = f("f2_did_results.csv").set_index("segment_metric")
facts = f("f2_facts.csv").set_index("fact").value
pnl = f("f1_branch_pnl.csv").set_index("branch")
rob = f("f2_robustness.csv")
gc = pd.read_csv(OUT / "f4_growth_capacity.csv", index_col=0)
rules = f("f5_branch_rules.csv")
ends = pd.read_csv(OUT / "f5_price_endings.csv", index_col=0).share_of_prices_ending_in_5_cents
sens = f("f5_price_sensitivity.csv").set_index("reading").implied_elasticity
scen = f("f5_pricing_scenarios.csv")
tot = scen[scen.branch == "Garden+Uptown"].set_index("case")["delta_gp_annual_flat (estimate)"]
be = scen.drop_duplicates("branch").set_index("branch").breakeven_unit_drop
dp = pd.read_csv(OUT / "f5_daypart_mix.csv", index_col=0)
ht = f("f5_holiday_test.csv").iloc[0]
bg = f("f5_background_discount.csv").set_index("segment").share_of_lines_with_10pct_discount
rk = f("f5_equal_cost_ranking.csv").set_index("branch")
sr = pd.read_csv(OUT / "stress_ranking.csv", index_col=0)
sp = f("stress_placebo_seeds.csv")
br = f("f1_margin_bridge.csv")
pil = f("f5_pilot_thresholds.csv")

checks = {
    "Garden margin 46.9%": f"{pnl.loc['Garden', 'gross_margin']:.1%}" == "46.9%",
    "Harbour margin 65.0%": f"{pnl.loc['Harbour', 'gross_margin']:.1%}" == "65.0%",
    "excess $19,485": round(vc["UPTOWN_BASIS total_excess_6m (measured)"]) == 19485,
    "10.9% of chain GP": f"{vc['UPTOWN_BASIS total_as_pct_chain_gp']:.1%}" == "10.9%",
    "37.2% of Garden GP": f"{vc['UPTOWN_BASIS garden_as_pct_garden_gp']:.1%}" == "37.2%",
    "$39.0k flat": f"{vc['UPTOWN_BASIS annual_flat_2xH1 (estimate)'] / 1000:.1f}" == "39.0",
    "$47.5k run-rate": f"{vc['UPTOWN_BASIS annual_june_run_rate_12xJune (estimate)'] / 1000:.1f}" == "47.5",
    "promo unit DiD +4.2%": f"{did.loc['promoted units', 'did']:+.1%}" == "+4.2%",
    "promo GP DiD -16.9%": f"{did.loc['promoted gp', 'did']:+.1%}" == "-16.9%",
    "block placebo p97.5 +19.6%": f"{did.loc['promoted units', 'block_placebo_did_p97.5']:+.1%}" == "+19.6%",
    "block placebo p99 +22.8%": f"{did.loc['promoted units', 'block_placebo_did_p99']:+.1%}" == "+22.8%",
    "break-even +29.3%": f"{float(facts['breakeven_unit_lift_for_15pct']):.1%}" == "29.3%",
    "robustness range -0.1..+8.9%": (f"{rob.promoted_units_did.min():+.1%}", f"{rob.promoted_units_did.max():+.1%}") == ("-0.1%", "+8.9%"),
    "holidays excluded: +4.8% overall, March +8.9%, May +0.8%": [f"{rob.set_index('check').promoted_units_did[k]:+.1%}" for k in [
        "matched days exclude public holidays", "block 1 only, matched days exclude public holidays",
        "block 2 only, matched days exclude public holidays"]] == ["+4.8%", "+8.9%", "+0.8%"],
    "slots >=10 txns/hr: 4 -> 19": (int(gc.loc["slots_avg_ge_10", "Jan-Feb"]), int(gc.loc["slots_avg_ge_10", "June"])) == (4, 19),
    "Harbour Tue 21h: 15.1 -> 22.2": (f"{gc.loc['harbour_tue_21h', 'Jan-Feb']:.1f}", f"{gc.loc['harbour_tue_21h', 'June']:.1f}") == ("15.1", "22.2"),
    "Harbour Fri 21h: 8.9 -> 15.5": (f"{gc.loc['harbour_fri_21h', 'Jan-Feb']:.1f}", f"{gc.loc['harbour_fri_21h', 'June']:.1f}") == ("8.9", "15.5"),
    "4 multipliers reproduce 45/45 each": (rules.exact_cent_matches == 45).all()
        and sorted(rules[rules.rule != "reference list"].multiplier.round(2)) == [0.96, 0.96, 1.05, 1.43],
    "price endings 100% / 11% / 4%": [f"{ends[b]:.0%}" for b in ["Garden", "Harbour", "Uptown"]] == ["100%", "11%", "4%"],
    "elasticity -0.25 / -0.52 / -1.04": [f"{sens[k]:.2f}" for k in ["measured unit lift (DiD)", "robustness: largest lift",
                                         "plausible upper lift (test inversion, ~95%)"]] == ["-0.25", "-0.52", "-1.04"],
    "price-gap value 17k / 14k / 8k / -2k": [round(tot[k] / 1000) for k in ["point estimate", "most price-sensitive robustness spec",
                                      "plausible bound (most price-sensitive)", "stress: elasticity -2.0 (not measured)"]] == [17, 14, 8, -2],
    "pilot thresholds 11.4-12.8% (menu 10.1-15.7%)": (lambda u: (f"{u[u.in_pilot].breakeven_unit_drop.min():.1%}", f"{u[u.in_pilot].breakeven_unit_drop.max():.1%}",
        f"{u.breakeven_unit_drop.min():.1%}", f"{u.breakeven_unit_drop.max():.1%}"))(pil[pil.branch == "Uptown"]) == ("11.4%", "12.8%", "10.1%", "15.7%"),
    "break-even drop 10% Garden, 13% Uptown": (f"{be['Garden']:.0%}", f"{be['Uptown']:.0%}") == ("10%", "13%"),
    "Garden break-even after cost fix 7%": f"{scen[scen.branch == 'Garden'].breakeven_unit_drop_if_costs_at_uptown_level.iloc[0]:.0%}" == "7%",
    "evening dine-in 72%, 44% of lines": (f"{1 - dp.loc['19-23', 'takeaway_share']:.0%}", f"{dp.loc['19-23', 'share_of_all_lines']:.0%}") == ("72%", "44%"),
    "holidays 3 of 15 at all branches, p = 0.03": (int(ht.holidays_standing_out_all_branches), int(ht.holidays_tested),
                                                     f"{ht.binomial_p_at_least_k:.2f}", f"{ht.expected_by_chance:.1f}") == (3, 15, "0.03", "0.7"),
    "10% discount $1,706": round(bg["discount given, 6 months (USD)"]) == 1706,
    "equal-cost margins 66.4 / 64.4 / 62.6": [f"{rk.loc[b, 'margin_at_uptown_unit_costs']:.1%}" for b in ["Harbour", "Garden", "Uptown"]]
        == ["66.4%", "64.4%", "62.6%"],
    "GP per order on equal costs: Garden $5.74 vs Uptown $5.45": (f"{sr.loc['Garden', 'gp_per_order_at_Uptown_costs']:.2f}",
        f"{sr.loc['Uptown', 'gp_per_order_at_Uptown_costs']:.2f}") == ("5.74", "5.45"),
    "Garden 2nd on every equal-cost metric": all(sr.loc["Garden", c] == 2 for c in sr.columns if c.startswith("rank_") and "_at_" in c),
    "seed stability: share reaching gap under 1%": sp.share_placebos_reaching_gap.max() < 0.01,
    "16 of 18 margin points from cost": (round(-br.change_pts.iloc[-1]), round((br.gross_margin.iloc[0] - br.gross_margin.iloc[-1]) * 100)) == (16, 18),
    "ranks reported 1/3/2 -> equal costs 1/2/3": (list(rk.loc[["Harbour", "Garden", "Uptown"], "rank_reported"]),
                                                  list(rk.loc[["Harbour", "Garden", "Uptown"], "rank_at_equal_costs"])) == ([1, 3, 2], [1, 2, 3]),
}
# Each checked value must also literally appear in the README (unicode minus allowed)
literals = ["46.9%", "65.0%", "$19,485", "10.9%", "37.2%", "$39.0k", "$47.5k", "+4.2%", "16.9%", "+19.6%", "+22.8%", "+29.3%", "+8.5%",
            "from 15.1 to 22.2", "from 8.9 to 15.5", "4 in January–February to 19 in June", "35.6% against 56.5%",
            "$5.74 vs Uptown's $5.45", "one recorded cost rule", "explains 16 of the 18 points", "ask finance what Garden's ×1.43 is", "got about +4%", "50% of consecutive IDs", "**3 → 2**", "Harbour × **1.43**", "Garden × **1.05**",
            "**−0.25**", "about −1.04", "**≈−$2k**", "its own** break-even drop", "11.4%–12.8%", "conditional scenarios, not forecasts", "no measurable unit response", "from 10% to 7%", "+8.9%", "+4.8% overall", "72% of those are dine-in",
            "(p ≈ 0.03)", "Reference (original unknown)", "$1,706"]
for lit in literals:
    checks[f"README mentions {lit}"] = lit in readme

failed = [k for k, ok in checks.items() if not ok]
for k, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + k)
sys.exit(1 if failed else 0)
