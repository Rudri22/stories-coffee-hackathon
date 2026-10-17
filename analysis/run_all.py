"""Reproduce every number in README.md: python analysis/run_all.py"""
import f1_garden_margin
import f2_promotions
import f3_demand_forecast
import rejected_checks
from common import OUT, data_quality_report

if __name__ == "__main__":
    dq = data_quality_report()
    dq.to_csv(OUT / "data_quality.csv", index=False)
    print("=== Data quality ===\n" + dq.to_string(index=False))
    for name, mod in [("F1 Garden margin", f1_garden_margin), ("F2 Promotions", f2_promotions), ("F3 Demand forecast", f3_demand_forecast), ("Rejected approaches", rejected_checks)]:
        print(f"\n=== {name} ===")
        mod.main()
