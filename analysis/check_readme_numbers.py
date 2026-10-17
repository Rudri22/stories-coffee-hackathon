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
    "block placebo p97.5 +17.3%": f"{did.loc['promoted units', 'block_placebo_did_p97.5']:+.1%}" == "+17.3%",
    "block placebo p99 +20.9%": f"{did.loc['promoted units', 'block_placebo_did_p99']:+.1%}" == "+20.9%",
    "break-even +29.3%": f"{float(facts['breakeven_unit_lift_for_15pct']):.1%}" == "29.3%",
    "robustness range -0.1..+8.5%": (f"{rob.promoted_units_did.min():+.1%}", f"{rob.promoted_units_did.max():+.1%}") == ("-0.1%", "+8.5%"),
    "slots >=10 txns/hr: 4 -> 19": (int(gc.loc["slots_avg_ge_10", "Jan-Feb"]), int(gc.loc["slots_avg_ge_10", "June"])) == (4, 19),
    "Harbour Tue 21h: 15.1 -> 22.2": (f"{gc.loc['harbour_tue_21h', 'Jan-Feb']:.1f}", f"{gc.loc['harbour_tue_21h', 'June']:.1f}") == ("15.1", "22.2"),
    "Harbour Fri 21h: 8.9 -> 15.5": (f"{gc.loc['harbour_fri_21h', 'Jan-Feb']:.1f}", f"{gc.loc['harbour_fri_21h', 'June']:.1f}") == ("8.9", "15.5"),
    "4 multipliers reproduce 45/45 each": (rules.exact_cent_matches == 45).all()
        and sorted(rules[rules.rule != "master list"].multiplier.round(2)) == [0.96, 0.96, 1.05, 1.43],
    "price endings 100% / 11% / 4%": [f"{ends[b]:.0%}" for b in ["Garden", "Harbour", "Uptown"]] == ["100%", "11%", "4%"],
    "elasticity -0.25 / -0.50 / -0.98": [f"{sens[k]:.2f}" for k in ["measured unit lift (DiD)", "robustness: largest lift",
                                         "plausible upper lift (test inversion, ~95%)"]] == ["-0.25", "-0.50", "-0.98"],
    "price-gap value 17k / 14k / 9k": [round(tot[k] / 1000) for k in ["point estimate", "most price-sensitive robustness spec",
                                      "plausible bound (most price-sensitive)"]] == [17, 14, 9],
    "break-even drop 10% Garden, 13% Uptown": (f"{be['Garden']:.0%}", f"{be['Uptown']:.0%}") == ("10%", "13%"),
    "evening dine-in 72%, 44% of lines": (f"{1 - dp.loc['19-23', 'takeaway_share']:.0%}", f"{dp.loc['19-23', 'share_of_all_lines']:.0%}") == ("72%", "44%"),
    "holidays 4 of 15, p = 0.005": (int(ht.holidays_outside_range), int(ht.holidays_tested), f"{ht.binomial_p_at_least_k:.3f}") == (4, 15, "0.005"),
    "10% discount $1,706": round(bg["discount given, 6 months (USD)"]) == 1706,
}
# Each checked value must also literally appear in the README (unicode minus allowed)
literals = ["46.9%", "65.0%", "$19,485", "10.9%", "37.2%", "$39.0k", "$47.5k", "+4.2%", "16.9%", "+17.3%", "+20.9%", "+29.3%", "+8.5%",
            "from 15.1 to 22.2", "from 8.9 to 15.5", "4 in January–February to 19 in June", "35.6% against 56.5%",
            "four multipliers reproduce every branch price and unit cost to the cent", "Harbour × **1.43**", "Garden × **1.05**",
            "**−0.25**", "about −0.98", "**≈$17k**", "≈$9k–$17k", "13% at Uptown, 10% at Garden", "72% of those are dine-in",
            "binomial p = 0.005", "$1,706"]
for lit in literals:
    checks[f"README mentions {lit}"] = lit in readme

failed = [k for k, ok in checks.items() if not ok]
for k, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + k)
sys.exit(1 if failed else 0)
