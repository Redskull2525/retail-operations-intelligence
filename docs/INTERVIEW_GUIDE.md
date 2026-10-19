# Interview Guide — Retail Operations Intelligence

Use this to explain the project confidently and **honestly**. Read the code alongside it; you should be able to explain every line you show.

> Golden rule: the data is **synthetic**. Never say "I helped a company save X" or "this increased sales by Y%". Say "I built and tested a pipeline and dashboard on synthetic retail data that mimics real problems."

---

## 1. Pitches

**30 seconds**
> "I built an end-to-end retail analytics project on synthetic data. A Python pipeline reads raw sales CSVs, validates them for problems like duplicates, missing regions, messy text, returns and wrong dates, cleans them, and loads a SQLite star schema. I wrote ten SQL business queries using CTEs and window functions, built a Streamlit dashboard, and documented a Power BI version. It has 26 pytest tests that run on GitHub Actions."

**60 seconds**
> "The scenario is a retailer with 20 products, 4 regions and 3 channels who wants trusted numbers on revenue, margin and stock. I generate 6,000 synthetic order lines with a fixed seed and deliberately inject known issues — 60 duplicate rows, 15 missing regions, 120 rows with inconsistent casing or spaces, 40 returns as negative quantities and 12 dates outside 2025. My pipeline counts each issue, handles it with a clear rule — for example returns are kept out of revenue and saved separately — and writes a data-quality report. Clean data goes into a star schema with two fact tables and three dimensions. On top of that I answer questions like monthly growth with LAG, top 5 products per region with RANK, and reorder alerts joined with last-90-day sales. KPI formulas live in one Python module that the dashboard and tests share, and the tests check that SQL and pandas give the same totals. I also fixed a bug in my first version where overstock could never happen."

---

## 2. Business problem

Managers need one trusted place to see: revenue trend and growth, best products/regions/channels, gross margin by category, and which items to reorder or stop over-stocking. Before any of that, they need to know the data is clean — so data quality is a first-class output, not an afterthought.

## 3. Architecture and data flow

```
generate_data.py → data/raw/*.csv (dirty on purpose)
        ↓
pipeline.py: Extract → Validate (count issues) → Clean (fix issues) → Load
        ↓                         ↓                         ↓
reports/data_quality_report.md   data/warehouse.db        data/processed/*.csv
                                  ↓                         ↓
                          run_sql.py (10 queries)   app.py (Streamlit) / Power BI
```

Why "validate" before "clean"? So we can **report** how many problems existed. If you clean first, you lose the evidence.

## 4. Dataset schema

**Raw sales** (`data/raw/sales_transactions_raw.csv`, 6,060 rows): order_id, order_date, region, channel, product_id, quantity, unit_price, discount_pct.

**Product catalog** (20 rows): product_id, product_name, category, unit_cost, unit_price, reorder_point, target_stock.

**Inventory snapshot** (80 rows = 20 products × 4 regions, dated 2025-12-31): snapshot_date, region, product_id, on_hand_units.

**Warehouse (star schema):**
- `dim_product`, `dim_region` (with surrogate `region_key`, includes `Unknown`), `dim_date` (`date_key` = YYYYMMDD)
- `fact_sales` — one row per completed order line; revenue, cost, gross_profit calculated in the pipeline
- `fact_inventory` — one row per product per region; inventory_value and stock_status calculated

**Grain** = what one row represents. Always state the grain when describing a fact table.

## 5. Data-quality checks and why

| Check | Found | Rule | Why this rule |
|---|---:|---|---|
| Exact duplicate rows | 60 | Drop, keep first | Double-counting inflates revenue |
| Conflicting order_ids (same id, different content) | 0 | Stop for review | We can't know which copy is right |
| Missing region | 15 | Keep, set `Unknown` | The sale happened; dropping it would understate revenue |
| Messy region / channel text | 60 / 60 | Strip spaces, match case-insensitively | `" west"` and `"West"` would otherwise be two groups |
| Negative quantity | 40 | Exclude from fact_sales, save to `returns_excluded.csv` | Not linked to original order; keeps revenue = completed sales |
| Date outside 2025 | 12 | Drop | Report covers 2025 only |
| Zero quantity, unknown product, discount outside 0–90% | 0 | Drop / stop | Can't calculate meaningful revenue |
| Inventory negative / unknown product / duplicate product-region | 0 | Stop for review | Would corrupt stock decisions |

After cleaning, `check_clean_sales()` confirms: no duplicate order_id, all quantities > 0, no negative revenue, all dates in 2025, only standard region/channel values. If any fail, the pipeline raises an error instead of loading bad data.

## 6. Important functions in plain English

**`src/generate_data.py`**
- `make_product_catalog(rng)` — loops over 4 categories × 5 names, picks a random cost and a markup of 1.25–1.85 to get price.
- `make_clean_sales(rng, products)` — creates 6,000 order lines. Dates are weighted so Oct–Dec sell more (festive season). Region and channel use fixed weights.
- `inject_quality_issues(rng, sales)` — shuffles row positions once and takes **separate slices** for each issue, so no row gets two issues and counts are exact. Then appends 60 copies and shuffles.
- `make_inventory_snapshot(rng, products)` — on hand drawn from 0 to 1.5 × target stock (bug fix: it used to stop at target stock, so Overstock was impossible).

**`src/pipeline.py`**
- `extract()` — `pd.read_csv` for the three files.
- `validate_sales()` — returns a dictionary of counts, e.g. `sales.duplicated().sum()`; for dates uses `pd.to_datetime(errors="coerce")` so bad dates become NaT instead of crashing.
- `standardize_text(value, valid_values, default)` — strip + lower, compare to each valid value in lower case, return the official spelling; blanks/unknown → default.
- `clean_sales()` — the cleaning steps in order, recording rows before/after each step, then calculates revenue, cost, gross_profit.
- `build_dim_date()`, `build_dim_region()`, `build_fact_sales()`, `build_fact_inventory()` — shape tables for the star schema (replace region text with `region_key`, add `date_key`).
- `load_to_sqlite()` — runs `sql/schema.sql` (drop + create tables) and inserts with `DataFrame.to_sql`. Dimensions are inserted before facts.
- `build_report()` — writes the Markdown report.

**`src/metrics.py`** — every KPI formula (`calculate_revenue`, `gross_margin_pct`, `average_order_value`, `monthly_revenue`, `stock_status`, `recommended_action`). One place → app, pipeline and tests all agree.

**`src/run_sql.py`** — splits `business_questions.sql` on `-- name:` lines, runs each with `pd.read_sql_query`, prints and saves Markdown.

**`app.py`** — loads processed CSVs (cached with `@st.cache_data`), sidebar filters build a boolean mask, KPI cards call `metrics.kpi_summary`, 5 tabs with Plotly charts, inventory actions, data-quality report, and CSV download.

## 7. SQL queries explained (`sql/business_questions.sql`)

1. **Monthly revenue & MoM** — CTE sums revenue per `year_month`; `LAG(revenue) OVER (ORDER BY year_month)` brings last month's value onto the same row; growth = (this − last) / last × 100.
2. **Top 5 products per region** — CTE totals revenue per region+product; `RANK() OVER (PARTITION BY region_name ORDER BY revenue DESC)` restarts numbering for each region; outer query keeps rank ≤ 5. (`RANK` gives ties the same number; `ROW_NUMBER` would not.)
3. **Gross margin by category** — `SUM(gross_profit) / SUM(revenue)`. Note: ratio of sums, not average of row margins.
4. **Channel mix %** — `SUM(SUM(revenue)) OVER ()` — the inner SUM is the GROUP BY total per channel, the outer window SUM with an empty `OVER ()` adds those up across all rows = grand total.
5. **AOV** — revenue / `COUNT(DISTINCT order_id)`, overall row via `UNION ALL` with the per-channel rows.
6. **Reorder alerts + last 90 days** — CTE of units sold where `order_date > DATE(MAX(order_date), '-90 days')`; `LEFT JOIN` so a product with no recent sales still appears (`COALESCE` → 0). Ordered so fast sellers come first.
7. **Duplicate check** — `GROUP BY order_id HAVING COUNT(*) > 1`; expected zero rows.
8. **Running total** — `SUM(revenue) OVER (ORDER BY year_month)`.
9. **Region performance** — orders, revenue, profit, margin per region including `Unknown`.
10. **Inventory status summary** — counts and stock value per status.

## 8. DAX measures (see POWER_BI_GUIDE.md)

- `Total Revenue = SUM(FactSales[revenue])`
- `Gross Margin % = DIVIDE([Gross Profit], [Total Revenue])` — DIVIDE avoids divide-by-zero errors.
- `Revenue Previous Month = CALCULATE([Total Revenue], DATEADD(DimDate[Date], -1, MONTH))` — CALCULATE changes the filter context.
- `Revenue MoM % = DIVIDE([Total Revenue] - [Revenue Previous Month], [Revenue Previous Month])`
- `Channel Share % = DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALL(FactSales[channel])))`

## 9. KPI formulas

| KPI | Formula | Value (synthetic, 2025) |
|---|---|---:|
| Revenue | Σ quantity × unit_price × (1 − discount) | ₹37,607,486 |
| Gross profit | revenue − quantity × unit_cost | ₹12,959,219 |
| Gross margin % | gross profit / revenue | 34.5% |
| Orders | distinct order_id | 5,948 |
| AOV | revenue / orders | ₹6,322.71 |
| Stock status | ≤ reorder point → Reorder; > target → Overstock; else Healthy | 15 / 37 / 28 |

## 10. Why each technology

- **Pandas** — industry-standard for reading CSVs and transforming tables in Python; easy to test.
- **SQLite** — a real SQL database in one file, no server to install; supports CTEs and window functions. Good for learning star schemas; in production I'd use PostgreSQL / SQL Server / a cloud warehouse.
- **Streamlit** — turns a Python script into an interactive web app quickly; deployable free on Streamlit Community Cloud.
- **Power BI** — what most BI teams in India use; the guide shows the same model in DAX.
- **pytest + GitHub Actions** — proves the pipeline works and keeps working after every change.

## 11. Testing (26 tests)

- `test_validation.py` — each injected issue is found with the exact count; a tiny hand-made table triggers every check; generator is reproducible.
- `test_cleaning.py` — row counts add up (6,060 − 60 − 12 − 40 = 5,948); no duplicates; no negative quantity/revenue; dates in 2025; text standardised; foreign keys valid; all three stock statuses exist.
- `test_metrics.py` — revenue formula and KPIs against hand-calculated numbers; empty-data edge cases; stock status boundaries (exactly at reorder point = Reorder; exactly at target = Healthy).
- `test_sql.py` — all 10 queries run; SQL totals equal pandas totals; warehouse has the 5 tables.
- `test_app.py` — Streamlit `AppTest` runs the app, checks 5 tabs and KPI cards, changes a filter, no exception.

Tests build data in a **temporary folder**, so they never overwrite committed files.

## 12. Limitations and ethics

- Synthetic data: seasonality, margins and weights were chosen by me in the generator, so "Oct–Dec is strongest" is a property of my generator, not a market insight. Say this openly.
- One product per order → AOV equals average line value.
- Returns excluded, not matched; gross profit is not net profit; single inventory snapshot with fixed rules (no forecasting, lead times or safety stock).
- Ethics: never present synthetic results as real business impact.

## 13. Interview questions with answers

1. **Walk me through your project.** → Use the 60-second pitch. *Follow-up: what was the hardest part?* — Making the issue counts exact and testable; I solved it by giving each issue its own non-overlapping set of rows.
2. **Why did you generate data instead of using a Kaggle dataset?** → I needed known, documented quality issues so I could prove the validation catches exactly them. With a seed it's fully reproducible. *Follow-up: what would change with real data?* — Issues would be unknown, so I'd profile first and add checks for whatever I find.
3. **What is a star schema? Why use it?** → Fact tables with numbers/events in the middle, dimension tables with descriptive attributes around them. Simple joins, fast aggregation, and it's what Power BI expects. *Follow-up: fact vs dimension?* — Facts are measurable events (sales lines); dimensions describe them (product, region, date).
4. **What is the grain of fact_sales?** → One completed order line; in this data one product per order.
5. **How did you handle duplicates?** → `drop_duplicates()` for exact copies (60). Also a check for same order_id with different content (0 found) — that would need investigation, not automatic deletion.
6. **Why not drop rows with missing region?** → They're valid sales; dropping 15 rows would understate revenue. Labelling `Unknown` keeps totals correct and makes the gap visible.
7. **How did you treat returns and why?** → Excluded from revenue and saved separately, because they aren't linked to the original order. *Follow-up: how would you do it with an original_order_id?* — Join returns to sales and report net revenue = gross sales − returned value, in the month of return.
8. **Explain LAG.** → A window function that reads a value from the previous row in a defined order without a self-join. I used it for last month's revenue.
9. **RANK vs ROW_NUMBER vs DENSE_RANK?** → ROW_NUMBER: always unique 1,2,3. RANK: ties share a number and leave gaps (1,1,3). DENSE_RANK: ties share without gaps (1,1,2).
10. **WHERE vs HAVING?** → WHERE filters rows before grouping; HAVING filters groups after aggregation (my duplicate check uses HAVING COUNT(*) > 1).
11. **Why LEFT JOIN in the reorder query?** → To keep products that need reordering even if they had no sales in the last 90 days; an INNER JOIN would silently drop them.
12. **How is gross margin calculated, and what's a common mistake?** → Sum of profit ÷ sum of revenue. Mistake: averaging row-level margins, which gives small orders the same weight as big ones.
13. **What does CALCULATE do in DAX?** → Evaluates an expression under a modified filter context, e.g. revenue for Online only, or for the previous month with DATEADD.
14. **Why put KPIs in metrics.py?** → One definition reused by app, pipeline and tests — avoids two versions of "revenue" disagreeing.
15. **How do you know your numbers are right?** → Tests compare SQL results with pandas results; hand-calculated unit tests; the Power BI reconciliation checklist compares to SQL output.
16. **What bug did you find?** → In v1, on-hand stock was random between 0 and target stock, so `on_hand > target_stock` (Overstock) was impossible. I widened the range and added a test that all three statuses occur.
17. **How would you scale this?** → Move SQLite to PostgreSQL or a cloud warehouse, schedule the pipeline (Airflow / cron / GitHub Actions schedule), load incrementally by date instead of full reload, and store the quality report history.
18. **How would you deploy the dashboard?** → Streamlit Community Cloud from the GitHub repo with `app.py` as the main file; data files are committed so it starts without running the pipeline.
19. **What would you add next?** → Returns analysis, multi-line orders, demand forecasting for reorder points, and alerting when a quality check fails.
20. **Is this real company data?** → No — it's synthetic, and I say that clearly in the README and app.

## 14. Common mistakes to avoid

- Claiming business impact ("saved ₹X") from synthetic data.
- Saying "I used machine learning" — this project has no ML.
- Not knowing the grain of a table, or mixing up fact and dimension.
- Averaging percentages instead of dividing sums.
- Forgetting that January MoM is empty (no previous month).
- Being unable to explain a line of code you show — read every file before the interview.
- Reading numbers from memory wrongly: keep `reports/sql_results.md` open when you demo.

## 15. Hands-on exercises (do these to prove understanding)

1. **New query:** add `q11_quarterly_revenue` to `business_questions.sql` (group by `dim_date.quarter`) and update the test that expects 10 queries.
2. **Change the reorder rule:** make "Reorder" mean `on_hand <= reorder_point * 1.2` in `metrics.stock_status`. Update `test_stock_status_rules`, re-run the pipeline and see how Q10 changes.
3. **New quality issue:** in the generator, inject 10 rows with an unknown `product_id` (e.g. `P999`). Confirm `unknown_product_id` = 10 in the report and that clean row count drops by 10; update tests.
4. **Return analysis:** add a Streamlit tab or SQL query on `returns_excluded.csv` showing returned units by product.
5. **Use ROW_NUMBER:** change Q2 to ROW_NUMBER and explain when results would differ.
6. **New KPI:** add `discount_given = Σ quantity × unit_price × discount_pct` to `metrics.py` with a unit test, and show it as a KPI card.
7. **Different seed:** change `SEED = 42` to `SEED = 7` in `src/generate_data.py`, re-run the generator, pipeline and tests. The issue counts stay the same by design; the money values change. (Change it back afterwards so the README numbers stay correct.)
8. **Power BI:** build the report from `docs/POWER_BI_GUIDE.md` and tick every row of the reconciliation checklist.
