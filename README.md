# Stories Coffee: Where the Margin Leaks

**EECE490 Stories Coffee Hackathon**

**Team members:** Rudy Abedulhadi · Karen El Helayel · Jad Faddoul

## Conclusion (one paragraph)
**Garden gave up about $16k of gross profit in six months (measured excess cost against Harbour's unit costs; ≈$32k a year only if volume stays flat, assumption A6), and nearly all of it behaves like a single branch-level cost rule rather than an operational problem.** Garden's recorded unit cost is **1.430× Harbour's on every one of 45 products** (1.46× the average of Harbour and Uptown). The ratio holds in every month, every category, and for both dine-in and takeaway. That pulls Garden's gross margin down to **46.9%**, against **65.0%** at Harbour and **62.6%** at Uptown. Product mix explains only 0.3 points of the 18-point gap and Garden's lower prices 1.8 points; **costs explain 16.0 points**. A multiplier this uniform does not look like waste, theft or spoilage. Those would vary by product perishability and over time. It points to one branch-level input: a supplier or distributor contract, or an overhead allocation booked into unit cost. **Recommended action:** before changing anything operational, Stories should audit how Garden's unit costs are produced, using 4 weeks of invoices for its top 10 products against Harbour's. The $16k is recoverable only if the gap turns out to be an avoidable purchase cost; if so, move Garden onto Harbour's supply terms. Raising Garden's prices instead is worth at most ≈$10k a year, and nothing if demand is price-sensitive (elasticity −2). Two secondary results. First, Harbour's 15% promotions on cold coffee and desserts showed no detectable rise in units (+4.2%, within chance) when they needed +29% to break even, so gross profit on those items fell about 17%. Second, a forecasting model beats a simple baseline by only a small margin.

> **Measured vs estimated.** Every number marked *(measured)* comes directly from the data via `analysis/`. Every $ "value" is an *(estimate)* resting on the assumptions in [§5](#5-assumptions-and-how-they-change-the-answer).

---

## 1. Business problem and why we chose it
Stories' data team already knows how many lattes each branch sells. We looked for something a sales dashboard would **not** show: why one of three branches earns far less per dollar sold, and whether that is fixable.

- **Chosen:** F1, branch margin leakage. It is the largest $ lever in the data, and it leads to a concrete, cheap first action.
- **Also tested:**
  - F2: did Harbour's 15% promotions pay off? No.
  - F3: can demand forecasting improve staffing? Brief answer: only slightly.

## 2. F1: Garden margin leak (main finding)
**Evidence** (`python analysis/f1_garden_margin.py` → `outputs/f1_*`):

| Branch | Revenue (measured) | Gross profit (measured) | Gross margin |
|---|---:|---:|---:|
| Harbour | $150,099 | $97,503 | **65.0%** |
| Garden | $99,531 | $46,696 | **46.9%** |
| Uptown | $55,554 | $34,795 | **62.6%** |

![margin](outputs/f1_margin_and_ratios.png)

**Margin bridge, Harbour → Garden** (`outputs/f1_margin_bridge.csv`, measured). It is a sequential decomposition on Garden's actual basket:

| Step | Gross margin | Change |
|---|---:|---:|
| Harbour actual | 64.96% | |
| Garden's product mix and discounts, at Harbour prices and costs | 64.65% | −0.31 pts |
| Garden's prices (4.8% below Harbour) | 62.88% | −1.77 pts |
| Garden's unit costs (1.43× Harbour) | **46.92%** | **−15.96 pts** |

**Challenging our first explanation** (R03, R04). We tested each alternative:

| Alternative explanation | Test | Result |
|---|---|---|
| Garden sells lower-margin items (mix) | Garden basket at Harbour prices and costs | Only −0.3 pts. **Rejected** |
| A supplier price rise during the period | Cost ratio by month | 1.4299–1.4301 in all 6 months. **Rejected** |
| Waste or spoilage of perishables | Cost ratio by category (perishable food vs drinks) | 1.4285–1.4311 for all 9 categories. **Rejected** |
| Packaging for takeaway | Cost ratio by order type | Exactly 1.4300 for both. **Rejected** |
| Duplicate lines distorting the picture | Margins with and without the 132 duplicates | Identical to 0.1 pt. **Rejected** |
| Premium ingredients at Garden | Premium inputs would usually justify higher prices; Garden is 4.8% *cheaper* | Not supported, but **cannot be ruled out** without recipe and supplier data |
| **Branch-level cost rule** (contract markup or overhead allocation) | A single constant multiplier on every item is what this cause would produce | **Consistent with all tests** |

Garden's weakest products sit around 29–34% margin: Sparkling Water, the Turkey & Cheese and Chicken Pesto sandwiches, Brownie and Cheesecake (`outputs/f1_garden_product_margins.csv`). Garden also sells more desserts than the other branches (11.0% of lines, versus 7.8% at Harbour and 6.9% at Uptown). At Garden's costs, desserts earn 35.6%, against 56.5% at Harbour (`outputs/f1_category_mix_and_margin.csv`).

**Value** (`outputs/f1_value_scenarios.csv`). All figures are **estimates**, annualised as 2× H1 2026 at flat volume (assumption A6):

| Action | Gross profit per year |
|---|---:|
| A. Garden unit costs at Harbour's level | **+$31.8k** |
| B. Close half of the cost gap | +$15.9k |
| C. Garden unit costs at Uptown's level | +$34.7k |
| D. Raise Garden prices to Harbour's (+5%), elasticity 0 / −1 / −2 | +$9.9k / +$5.0k / +$0.3k |

**Costs and tradeoffs:**
- The audit itself is cheap: invoices and the costing sheet.
- Switching supplier may change quality or reliability, so taste-test and check delivery.
- The price route (D) risks traffic. 94% of known customers visit two or more branches, so they would notice a price change (`outputs/f1_shared_customers.csv`).

**Practical test before wider use** (R09):
1. Pull 4 weeks of supplier invoices for Garden's and Harbour's top 10 products by volume, and compare the landed cost per unit.
2. Ask finance how "Unit Cost" is calculated for each branch.
3. If the gap is a real purchase price, move 3 products (for example Iced Latte, Butter Croissant, Brownie) onto Harbour's supplier for 4 weeks. Check that recorded unit cost drops while sales per day and the product mix stay within their normal weekly range.

## 3. F2: Harbour's 15% promotions did not pay for themselves
**What the data shows** (`outputs/f2_facts.csv`, measured):
- The 15% discount appears **only at Harbour**, on **16 days** (12–19 March and 12–19 May), and **only on Cold Coffee and Desserts**: Iced Latte, Iced Americano, Cold Brew, Iced Mocha, Coffee Frappe, Brownie, Cheesecake, Frozen Yoghurt and Tiramisu.
- On those days, every one of those units was discounted.
- A separate 10% discount runs at a steady background rate at all three branches.

**Design: a difference-in-differences comparison** (`analysis/f2_promotions.py`). For each promo day, we compare Harbour's sales with the same weekday 1–3 weeks before and after. We subtract the same comparison for Garden and Uptown on the same categories and days, which removes chain-wide effects such as holidays and weather. A placebo check runs the identical method on 1,000 random sets of 16 non-promo days, to show how big a "result" appears by chance.

| Harbour, promo days vs matched days | Harbour change | Garden+Uptown change | **Difference-in-differences** | Chance range (95% of placebos) | Placebos as extreme |
|---|---:|---:|---:|---:|---:|
| Units of promoted items | −3.3% | −7.5% | **+4.2%** | −13.5% … +16.5% | 61% |
| Gross profit on promoted items | −24.7% | −7.9% | **−16.9%** | −15.1% … +15.9% | **3.4%** |
| Units of other items (halo?) | −2.6% | −1.6% | −1.0% | −9.6% … +11.1% | 85% |
| Transactions | −3.6% | −3.4% | −0.2% | −8.1% … +9.1% | 96% |

(`outputs/f2_did_results.csv`, per-day detail in `outputs/f2_did_by_day.csv`)

- **Break-even:** promoted items earn a 66.1% margin at full price, so a 15% discount needs **+29% more units** just to hold gross profit level. The measured lift, +4.2%, is not distinguishable from zero.
- **Result:** on the promoted items, Harbour earned **$1,604** of gross profit against **$2,178** on matched days. Net of the same-day dip at the other branches, that is **−16.9%, about $370** over 16 days. No halo effect on other items and no extra transactions were detected.
- **Pull-forward check:** in the 7 days after each block, promoted units at Harbour ran 8.9% below matched days, net of the control branches. That is a point estimate with no placebo test, so read it as a warning sign, not a result.
- **The $ size is small:** $470 of 15% discount was given. Total discounting over 6 months was $2,176. The value of this finding is the *decision rule*, not the money already lost: **stop blanket 15% category discounts**. Promotions should be judged against the +29% break-even, using the same branch-vs-control test before rolling one out.
- **Not proof of cause** (R10): promo dates were not randomised. Harbour may have scheduled them for weeks it expected to be weak, and with only 16 days a small true lift cannot be ruled out.

## 4. F3: Demand forecast for staffing (tested, modest value)
Target: transactions per branch per hour, 07:00–23:00. **Trained on January–May. June was held out and never used for fitting** (R07).

- **Baseline:** the mean of the last 4 same-weekday, same-hour values.
- **Model:** a Poisson GLM using branch×hour, branch×weekday and branch×trend.

| Holdout (June) | Baseline WAPE | Model WAPE | Baseline bias | Model bias |
|---|---:|---:|---:|---:|
| Branch-day | 11.5% | **9.0%** | −7.5% | **+0.4%** |
| Branch-hour | 39.3% | **35.9%** | −7.5% | +0.4% |
| Tuesdays (branch-hour) | 33.1% | 30.2% | −6.9% | +0.1% |

We also tested a **trend-adjusted baseline**: the seasonal-naive forecast multiplied by each branch's growth over the last 4 training weeks. It reaches 10.2% branch-day WAPE with +0.7% bias, but it is worse at the hourly level (40.0%). Full results are in `outputs/f3_holdout_metrics.csv`.

![forecast](outputs/f3_forecast_and_heatmap.png)

- **Measured patterns:**
  - Tuesday carries **1.61×** the transactions of the average other weekday. That holds in **every one of 25 weeks** (range 1.44–1.81), so it is not driven by outliers.
  - The 21:00 hour alone carries 12.6% of all lines (`outputs/f3_hour_share_of_lines.csv`).
  - Monthly transactions grew 52% from January to June (`outputs/f3_monthly_transactions.csv`), at all three branches.
- **Why the value is modest:**
  - A branch averages only 2.1 (Uptown) to 5.3 (Harbour) transactions an hour; the 90th percentile is 4–10 (`outputs/f3_hourly_volume_and_tuesday_ratio.csv`).
  - The baseline's main error is that it lags the growth trend (−7.5% bias). The model fixes that, and the trend adjustment alone closes about half of the daily-error gap.
  - In a staffing simulation (assumption A7: one staff member per 15 transactions an hour), short-staffed hours in June were 15 with the baseline, 13 with the trend adjustment and 12 with the model. The model plan cost 9 extra staff-hours (`outputs/f3_staffing_holdout.csv`).
  - **We do not recommend investing in a complex forecasting system.** The measured gain over simple rules is a few staff-hours a month. A roster built on the stable Tuesday and 19:00–22:00 peaks, reviewed monthly for growth, is the practical version.
- **Not tried, by design:** a gradient-boosted tree model. Trees cannot extrapolate a growth trend, and the trend is the main thing a forecast must capture here. This is a reasoned choice, not a tested result.

## 4b. Approaches we considered and rejected
Each idea below would only be worth pursuing if the data showed a gap to close. We measured it, and it didn't (`outputs/rejected_checks.csv`, via `analysis/rejected_checks.py`):

| Idea | Measured | Why rejected |
|---|---|---|
| Cross-sell food with drinks at a lagging branch | Food attach rate on drink orders is 40.2% / 41.8% / 40.9% (Harbour / Garden / Uptown) | No branch lags, so there is no gap to close |
| Churn prediction / win-back | 98.5% of known customers made 2+ visits | There is no churn problem in this window to model |
| Push takeaway or dine-in for higher spend | Average order value: $9.01 dine-in vs $9.00 takeaway | No difference in spend |
| Push loyalty sign-up for bigger baskets | Average order value: $9.00 known vs $9.02 anonymous | No basket difference (the loyalty programme may still have other value) |
| A "query my database" chatbot | — | The brief says it earns no credit on its own |

## 5. Assumptions and how they change the answer
| ID | Assumption | If it is wrong… |
|---|---|---|
| A1 | "Unit Cost" is Stories' per-unit cost of goods as recorded by finance | If it includes a rent or overhead *allocation*, the $16k is not cash to recover. The action becomes "fix the costing so Garden's menu and pricing decisions aren't distorted", and scenario D (pricing) becomes the wrong move. **This is the assumption most likely to change the recommendation.** |
| A2 | The 132 identical lines ($741 of revenue) are double-logged | Margins change by under 0.1 pt, so it doesn't matter |
| A3 | A blank Customer ID means a non-loyalty customer | Affects only the "94% visit 2+ branches" statistic |
| A4 | Branch names are anonymised; Lebanese context (USD pricing, imported inputs, generator power) is background only | Not used as evidence |
| A5 | Price elasticity at Garden is unknown, so we swept 0 to −2 | Pricing value ranges from $10k to $0 a year |
| A6 | Annual = 2× H1 at flat volume | Conservative: transactions grew 52% from January to June |
| A7 | One staff member handles 10–20 transactions an hour | Changes the staffing numbers, not the forecast ranking |

## 6. Weak areas, uncertainty and missing information
- **Missing information:** supplier invoices, how unit cost is calculated, rent and labour, the campaign calendar, holidays, stock-outs, and weather. With these, F1 becomes a confirmed cash number and F2 becomes causal.
- **Six months only:** no seasonality across a full year. Summer 2026 may differ.
- The F2 placebo test assumes promo days are otherwise comparable to random days. The control branches absorb chain-wide shocks, but not shocks that hit only Harbour.
- **Probable dataset artefact:** 81% of known customers first appear in January–February, and new IDs fall to about 20 in June, from a fixed pool of 3,494 IDs. We treat this as a construction artefact, not a real acquisition collapse, and draw no conclusions from it (`outputs/rejected_checks.csv`).
- The data's exact ratios and the absence of any price change suggest the costing may be formula-driven. We treat that as a finding to verify, not a certainty.

## 7. Reproduce
```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
# place stories_transactions.csv in data/
python analysis/run_all.py      # rewrites every table and chart in outputs/ (~2 min, mostly the F2 placebo test)
```

| Path | Contents |
|---|---|
| `analysis/common.py` | Loading, cleaning (de-duplication), data-quality checks → `outputs/data_quality.csv` |
| `analysis/f1_garden_margin.py` | Branch P&L, unit ratios, margin bridge, alternative-explanation tests, value scenarios |
| `analysis/f2_promotions.py` | Promo facts, difference-in-differences vs control branches, placebo test, break-even |
| `analysis/f3_demand_forecast.py` | Baselines vs Poisson model, June holdout, staffing simulation |
| `analysis/rejected_checks.py` | Evidence for the rejected approaches in §4b |

**Data quality** (`outputs/data_quality.csv`, measured): 51,177 lines and 33,887 transactions from 2026-01-01 to 2026-06-30. Revenue and gross profit reconcile on 100% of lines. No transaction has conflicting header fields. Each product has one price and one unit cost per branch for the whole period. 132 exact duplicate lines were removed. 36.5% of lines have no Customer ID.
