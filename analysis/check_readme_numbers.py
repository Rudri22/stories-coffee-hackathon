"""Consistency test: every headline number in README.md must match the generated outputs.
Run after run_all.py:  python analysis/check_readme_numbers.py   (exit code 1 on any mismatch)"""
import sys

import pandas as pd

from common import OUT, ROOT

readme = (ROOT / "README.md").read_text(encoding="utf-8")
f = lambda name: pd.read_csv(OUT / name)
vc = f("f4_value_context.csv").set_index("item").value
did = f("f2_did_results.csv").set_index("segment_metric")
facts = f("f2_facts.csv").set_index("fact").value
pnl = f("f1_branch_pnl.csv").set_index("branch")
rob = f("f2_robustness.csv")
gc = pd.read_csv(OUT / "f4_growth_capacity.csv", index_col=0)

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
}
# Each checked value must also literally appear in the README (unicode minus allowed)
literals = ["46.9%", "65.0%", "$19,485", "10.9%", "37.2%", "$39.0k", "$47.5k", "+4.2%", "16.9%", "+17.3%", "+20.9%", "+29.3%", "+8.5%",
            "from 15.1 to 22.2", "from 8.9 to 15.5", "4 in January–February to 19 in June", "35.6% against 56.5%"]
for lit in literals:
    checks[f"README mentions {lit}"] = lit in readme

failed = [k for k, ok in checks.items() if not ok]
for k, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + k)
sys.exit(1 if failed else 0)
