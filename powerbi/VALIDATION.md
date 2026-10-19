# Power BI validation record

> All numbers are from **synthetic data** (seed 42). This file records what was actually run on
> 2026-10-19 on the author's Windows 11 PC; nothing here is estimated.

## Environment

| Item | Value |
|---|---|
| Power BI Desktop | 2.158.1304.0 (September 2026), Microsoft Store edition |
| Project format | PBIP with a **TMDL** semantic model (`RetailOperations.SemanticModel/definition/`, compatibility level 1601; Desktop upgraded it to 1606 in memory) and a **PBIR** report (`RetailOperations.Report/definition/`; schemas report 3.1.0, page 2.0.0, visualContainer 2.5.0) |
| How the files were produced | `tools/build_semantic_model.ps1` (the Tabular Object Model DLL that ships with Desktop + `TmdlSerializer`, with a deserialize round-trip check) and `tools/build_report.py` |
| Schema check | All 52 JSON files that declare a `$schema` were validated against Microsoft's public JSON schemas with `jsonschema`: 0 failures |

## 1. Does it open?

`RetailOperations.pbip` was opened in Power BI Desktop. No keystrokes or mouse clicks were sent; the window was captured with the Win32 `PrintWindow` API.

| Attempt | Result | Fix |
|---|---|---|
| 1 | Dialog "Issues were found - M Engine error: Invalid identifier" | Power Query field access `[Discount %]` is not a valid identifier; changed to `[#"Discount %"]` |
| 2 | Opened; one measure failed: "The syntax for 'PreviousMonth' is incorrect" | `PREVIOUSMONTH` is a DAX function, so it cannot be a variable name; renamed the variable to `PrevMonthRevenue` |
| 3 to 8 | **Opened cleanly**: 4 pages, 7 tables, no error dialog, no broken visuals | none needed |

On open, Desktop shows the banner "Some of the tables have incomplete or no data". This is expected: a PBIP holds no data, and the data cache (`.pbi/cache.abf`) is git-ignored. Clicking **Refresh** loads the data.

## 2. Refresh

The refresh ran through Desktop's local Analysis Services instance (`tools/run_dax_checks.ps1 -Refresh`, which calls `Model.RequestRefresh(Full)` and then `SaveChanges()`).

Result: all 7 tables reached state `Ready`, with no refresh errors and no measure errors. Each run took 8 to 40 seconds (6 runs).
Row counts after the refresh: FactSales **5,948**, FactInventory **80**, DimDate **365**.

## 3. Reconciliation: DAX vs SQL

The script ran DAX queries (`EVALUATE ROW` and `SUMMARIZECOLUMNS`) against the refreshed model. `tools/reconcile.py` compared the results with SQL run on `data/warehouse.db`; returns were checked against `data/processed/returns_excluded.csv`.
Tolerance: 0.01 for money, 0.0001 (0.01 percentage points) for ratios, and exact for counts.
Raw DAX output: [`tools/dax_results.json`](tools/dax_results.json).

**Headline checks (the same figures appear in `reports/sql_results.md`)**

| Measure | DAX result | SQL result | Match? |
|---|---:|---:|:---:|
| Total Revenue | ₹37,607,486.05 | ₹37,607,486.05 | yes |
| Gross Profit | ₹12,959,219.05 | ₹12,959,219.05 | yes |
| Gross Margin % | 34.46% | 34.46% (report rounds to 34.5) | yes |
| Orders | 5,948 | 5,948 | yes |
| Avg Order Value | ₹6,322.71 | ₹6,322.71 | yes |
| Units Sold | 17,781 | 17,781 | yes |
| Gross Margin %: Home / Electronics / Office / Lifestyle | 38.34 / 34.43 / 33.26 / 32.21% | 38.3 / 34.4 / 33.3 / 32.2 (Q3) | yes |
| Revenue Share %: Online / Retail Store / Marketplace | 45.39 / 35.91 / 18.69% | 45.4 / 35.9 / 18.7 (Q4) | yes |
| MoM Growth %: Oct 2025 | 19.42% | 19.4 (Q1) | yes |
| Revenue: Dec 2025 | ₹4,380,829.10 | ₹4,380,829.10 (Q1) | yes |
| Revenue YTD: Dec 2025 | ₹37,607,486.05 | ₹37,607,486.05 (Q8) | yes |
| Reorder / Healthy / Overstock rows | 15 / 37 / 28 | 15 / 37 / 28 (Q10) | yes |
| Inventory Value | ₹7,027,455 | ₹7,027,455 (Q10) | yes |
| Returns: units / lines | 87 / 40 | 87 / 40 | yes |

**Full table: every measure, overall and by month, category, channel, region and stock status**

<details><summary>126 checks (click to expand)</summary>

| Measure (filter) | DAX result | SQL result | Match? |
|---|---:|---:|:---:|
| Total Revenue | ₹37,607,486.05 | ₹37,607,486.05 | yes |
| Total Cost | ₹24,648,267.00 | ₹24,648,267.00 | yes |
| Gross Profit | ₹12,959,219.05 | ₹12,959,219.05 | yes |
| Gross Margin % | 34.46% | 34.46% | yes |
| Orders | 5,948 | 5,948 | yes |
| Units Sold | 17,781 | 17,781 | yes |
| Avg Order Value | ₹6,322.71 | ₹6,322.71 | yes |
| Revenue Share % | 100.00% | 100.00% | yes |
| Inventory Value | ₹7,027,455.00 | ₹7,027,455.00 | yes |
| On Hand Units | 5,268 | 5,268 | yes |
| Reorder Alerts | 15 | 15 | yes |
| Overstock Alerts | 28 | 28 | yes |
| Healthy Items | 37 | 37 | yes |
| Units To Reorder | 1,120 | 1,120 | yes |
| Excess Units | 546 | 546 | yes |
| Alert On Hand Units | 3,191 | 3,191 | yes |
| Alert Inventory Value | ₹4,175,168.00 | ₹4,175,168.00 | yes |
| Returned Lines | 40 | 40 | yes |
| Returns Units | 87 | 87 | yes |
| Returns Value | ₹204,334.65 | ₹204,334.65 | yes |
| Total Revenue — 2025-01 | ₹2,630,075.25 | ₹2,630,075.25 | yes |
| Revenue PM — 2025-01 | BLANK | BLANK | yes |
| MoM Growth % — 2025-01 | BLANK | BLANK | yes |
| Revenue YTD — 2025-01 | ₹2,630,075.25 | ₹2,630,075.25 | yes |
| Total Revenue — 2025-02 | ₹2,095,186.25 | ₹2,095,186.25 | yes |
| Revenue PM — 2025-02 | ₹2,630,075.25 | ₹2,630,075.25 | yes |
| MoM Growth % — 2025-02 | -20.34% | -20.34% | yes |
| Revenue YTD — 2025-02 | ₹4,725,261.50 | ₹4,725,261.50 | yes |
| Total Revenue — 2025-03 | ₹2,738,424.80 | ₹2,738,424.80 | yes |
| Revenue PM — 2025-03 | ₹2,095,186.25 | ₹2,095,186.25 | yes |
| MoM Growth % — 2025-03 | 30.70% | 30.70% | yes |
| Revenue YTD — 2025-03 | ₹7,463,686.30 | ₹7,463,686.30 | yes |
| Total Revenue — 2025-04 | ₹2,820,844.65 | ₹2,820,844.65 | yes |
| Revenue PM — 2025-04 | ₹2,738,424.80 | ₹2,738,424.80 | yes |
| MoM Growth % — 2025-04 | 3.01% | 3.01% | yes |
| Revenue YTD — 2025-04 | ₹10,284,530.95 | ₹10,284,530.95 | yes |
| Total Revenue — 2025-05 | ₹2,728,847.95 | ₹2,728,847.95 | yes |
| Revenue PM — 2025-05 | ₹2,820,844.65 | ₹2,820,844.65 | yes |
| MoM Growth % — 2025-05 | -3.26% | -3.26% | yes |
| Revenue YTD — 2025-05 | ₹13,013,378.90 | ₹13,013,378.90 | yes |
| Total Revenue — 2025-06 | ₹2,772,608.85 | ₹2,772,608.85 | yes |
| Revenue PM — 2025-06 | ₹2,728,847.95 | ₹2,728,847.95 | yes |
| MoM Growth % — 2025-06 | 1.60% | 1.60% | yes |
| Revenue YTD — 2025-06 | ₹15,785,987.75 | ₹15,785,987.75 | yes |
| Total Revenue — 2025-07 | ₹2,750,605.65 | ₹2,750,605.65 | yes |
| Revenue PM — 2025-07 | ₹2,772,608.85 | ₹2,772,608.85 | yes |
| MoM Growth % — 2025-07 | -0.79% | -0.79% | yes |
| Revenue YTD — 2025-07 | ₹18,536,593.40 | ₹18,536,593.40 | yes |
| Total Revenue — 2025-08 | ₹3,184,227.25 | ₹3,184,227.25 | yes |
| Revenue PM — 2025-08 | ₹2,750,605.65 | ₹2,750,605.65 | yes |
| MoM Growth % — 2025-08 | 15.76% | 15.76% | yes |
| Revenue YTD — 2025-08 | ₹21,720,820.65 | ₹21,720,820.65 | yes |
| Total Revenue — 2025-09 | ₹3,344,105.65 | ₹3,344,105.65 | yes |
| Revenue PM — 2025-09 | ₹3,184,227.25 | ₹3,184,227.25 | yes |
| MoM Growth % — 2025-09 | 5.02% | 5.02% | yes |
| Revenue YTD — 2025-09 | ₹25,064,926.30 | ₹25,064,926.30 | yes |
| Total Revenue — 2025-10 | ₹3,993,500.60 | ₹3,993,500.60 | yes |
| Revenue PM — 2025-10 | ₹3,344,105.65 | ₹3,344,105.65 | yes |
| MoM Growth % — 2025-10 | 19.42% | 19.42% | yes |
| Revenue YTD — 2025-10 | ₹29,058,426.90 | ₹29,058,426.90 | yes |
| Total Revenue — 2025-11 | ₹4,168,230.05 | ₹4,168,230.05 | yes |
| Revenue PM — 2025-11 | ₹3,993,500.60 | ₹3,993,500.60 | yes |
| MoM Growth % — 2025-11 | 4.38% | 4.38% | yes |
| Revenue YTD — 2025-11 | ₹33,226,656.95 | ₹33,226,656.95 | yes |
| Total Revenue — 2025-12 | ₹4,380,829.10 | ₹4,380,829.10 | yes |
| Revenue PM — 2025-12 | ₹4,168,230.05 | ₹4,168,230.05 | yes |
| MoM Growth % — 2025-12 | 5.10% | 5.10% | yes |
| Revenue YTD — 2025-12 | ₹37,607,486.05 | ₹37,607,486.05 | yes |
| Total Revenue — Electronics | ₹9,006,702.65 | ₹9,006,702.65 | yes |
| Gross Profit — Electronics | ₹3,100,673.65 | ₹3,100,673.65 | yes |
| Gross Margin % — Electronics | 34.43% | 34.43% | yes |
| Total Revenue — Home | ₹8,868,535.60 | ₹8,868,535.60 | yes |
| Gross Profit — Home | ₹3,399,797.60 | ₹3,399,797.60 | yes |
| Gross Margin % — Home | 38.34% | 38.34% | yes |
| Total Revenue — Lifestyle | ₹9,887,385.90 | ₹9,887,385.90 | yes |
| Gross Profit — Lifestyle | ₹3,184,418.90 | ₹3,184,418.90 | yes |
| Gross Margin % — Lifestyle | 32.21% | 32.21% | yes |
| Total Revenue — Office | ₹9,844,861.90 | ₹9,844,861.90 | yes |
| Gross Profit — Office | ₹3,274,328.90 | ₹3,274,328.90 | yes |
| Gross Margin % — Office | 33.26% | 33.26% | yes |
| Orders — Marketplace | 1,117 | 1,117 | yes |
| Total Revenue — Marketplace | ₹7,029,688.60 | ₹7,029,688.60 | yes |
| Revenue Share % — Marketplace | 18.69% | 18.69% | yes |
| Avg Order Value — Marketplace | ₹6,293.36 | ₹6,293.36 | yes |
| Orders — Online | 2,731 | 2,731 | yes |
| Total Revenue — Online | ₹17,071,722.25 | ₹17,071,722.25 | yes |
| Revenue Share % — Online | 45.39% | 45.39% | yes |
| Avg Order Value — Online | ₹6,251.09 | ₹6,251.09 | yes |
| Orders — Retail Store | 2,100 | 2,100 | yes |
| Total Revenue — Retail Store | ₹13,506,075.20 | ₹13,506,075.20 | yes |
| Revenue Share % — Retail Store | 35.91% | 35.91% | yes |
| Avg Order Value — Retail Store | ₹6,431.46 | ₹6,431.46 | yes |
| Orders — East | 1,097 | 1,097 | yes |
| Total Revenue — East | ₹6,845,100.40 | ₹6,845,100.40 | yes |
| Gross Profit — East | ₹2,346,011.40 | ₹2,346,011.40 | yes |
| Gross Margin % — East | 34.27% | 34.27% | yes |
| Revenue Share % — East | 18.20% | 18.20% | yes |
| Orders — North | 1,504 | 1,504 | yes |
| Total Revenue — North | ₹9,829,235.95 | ₹9,829,235.95 | yes |
| Gross Profit — North | ₹3,377,646.95 | ₹3,377,646.95 | yes |
| Gross Margin % — North | 34.36% | 34.36% | yes |
| Revenue Share % — North | 26.14% | 26.14% | yes |
| Orders — South | 1,431 | 1,431 | yes |
| Total Revenue — South | ₹8,980,680.05 | ₹8,980,680.05 | yes |
| Gross Profit — South | ₹3,112,659.05 | ₹3,112,659.05 | yes |
| Gross Margin % — South | 34.66% | 34.66% | yes |
| Revenue Share % — South | 23.88% | 23.88% | yes |
| Orders — Unknown | 15 | 15 | yes |
| Total Revenue — Unknown | ₹98,358.55 | ₹98,358.55 | yes |
| Gross Profit — Unknown | ₹32,596.55 | ₹32,596.55 | yes |
| Gross Margin % — Unknown | 33.14% | 33.14% | yes |
| Revenue Share % — Unknown | 0.26% | 0.26% | yes |
| Orders — West | 1,901 | 1,901 | yes |
| Total Revenue — West | ₹11,854,111.10 | ₹11,854,111.10 | yes |
| Gross Profit — West | ₹4,090,305.10 | ₹4,090,305.10 | yes |
| Gross Margin % — West | 34.51% | 34.51% | yes |
| Revenue Share % — West | 31.52% | 31.52% | yes |
| Rows — Healthy | 37 | 37 | yes |
| On Hand Units — Healthy | 2,077 | 2,077 | yes |
| Inventory Value — Healthy | ₹2,852,287.00 | ₹2,852,287.00 | yes |
| Rows — Overstock | 28 | 28 | yes |
| On Hand Units — Overstock | 3,000 | 3,000 | yes |
| Inventory Value — Overstock | ₹3,888,594.00 | ₹3,888,594.00 | yes |
| Rows — Reorder | 15 | 15 | yes |
| On Hand Units — Reorder | 191 | 191 | yes |
| Inventory Value — Reorder | ₹286,574.00 | ₹286,574.00 | yes |

126 of 126 checks match.

</details>

The same 126 checks also passed on each of the other refresh runs (one run per captured page).

## 4. Screenshots

Desktop opens on the report's active page. To capture each page, `activePageName` was set in `pages.json`, then Desktop was relaunched, the data refreshed and the window captured; no clicks or keystrokes were sent.
The images in `assets/` are crops of those real captures (Power BI Desktop 2.158, refreshed data):

- `assets/powerbi_overview.png`: Executive Overview
- `assets/powerbi_products.png`: Product Profitability
- `assets/powerbi_inventory.png`: Inventory Alerts
- `assets/powerbi_data_quality.png`: Data Quality

On this machine, Desktop displayed the `₹#,0` format with Indian digit grouping (₹3,76,07,486 is ₹37,607,486).

## 5. What was NOT done

- **No `.pbix` file was produced.** Saving a .pbix requires Desktop's GUI (File > Save as), and that step was not automated.
  The PBIP folder is the source; producing the .pbix is a one-click manual step (see `docs/POWER_BI_GUIDE.md`).
- The project was never saved from Desktop, so the files are exactly what the build scripts wrote.
  The first time you save, Desktop may add `lineageTag`s and `.pbi/` settings files.
- Slicer interactions were not tested, because that would need clicks. The measures were tested with DAX instead.
- The report was not published to the Power BI service.
