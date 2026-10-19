# Power BI Guide (beginner, step by step)

Build a Power BI report on the **same clean, synthetic data** that the Python pipeline produces, then prove it matches the SQL results.

> The `.pbix` file is not in the repo. Follow these steps in **Power BI Desktop** (free, Windows) to build it yourself. All data is synthetic.

## 0. Before you start

Run the pipeline (or use the committed files):

```bash
python src/generate_data.py
python src/pipeline.py
python src/run_sql.py      # gives you reports/sql_results.md to reconcile against
```

Files you will import from `data/processed/`:

| File | Rows | Columns |
|---|---:|---|
| `fact_sales.csv` | 5,948 | order_id, date_key, order_date, product_id, region_key, channel, quantity, unit_price, discount_pct, revenue, cost, gross_profit |
| `fact_inventory.csv` | 80 | snapshot_date_key, product_id, region_key, on_hand_units, inventory_value, stock_status |
| `dim_product.csv` | 20 | product_id, product_name, category, unit_cost, unit_price, reorder_point, target_stock |
| `dim_region.csv` | 5 | region_key, region_name |
| `returns_excluded.csv` (optional) | 40 | order_id, order_date, region, channel, product_id, quantity, unit_price, discount_pct |

`dim_date.csv` also exists, but in this guide we build the date table in **DAX** (step 4) because that is what most Power BI teams do. Use one or the other, not both.

## 1. Import the CSVs

1. **Home → Get data → Text/CSV**.
2. Pick `fact_sales.csv` → **Transform Data** (not Load) so Power Query opens.
3. Repeat for `fact_inventory.csv`, `dim_product.csv`, `dim_region.csv` (Power Query: **New Source → Text/CSV**).

## 2. Power Query steps (Transform Data)

For each query, check the data types (click the icon left of each column header):

**fact_sales**
- `order_id`, `product_id`, `channel` → Text
- `date_key`, `region_key`, `quantity` → Whole Number
- `order_date` → **Date**
- `unit_price`, `discount_pct`, `revenue`, `cost`, `gross_profit` → Decimal Number (or Fixed Decimal for money)
- Rename query to **FactSales**.

**fact_inventory**
- `snapshot_date_key`, `region_key`, `on_hand_units` → Whole Number; `inventory_value` → Decimal; others Text.
- Rename to **FactInventory**.

**dim_product** → rename to **DimProduct**; `unit_cost`, `unit_price` Decimal; `reorder_point`, `target_stock` Whole Number.

**dim_region** → rename to **DimRegion**; `region_key` Whole Number.

Quick quality checks you can do in Power Query (View → enable *Column quality* and *Column distribution*):
- `order_id` should show **5,948 distinct, 5,948 unique** (no duplicates).
- `quantity` and `revenue` should have no negative values (Column profile → min).
- No errors / empty values in any column.

Click **Close & Apply**.

## 3. Relationships (star schema)

Go to **Model view** and create (drag column onto column):

| From (many side) | To (one side) | Cardinality | Filter direction |
|---|---|---|---|
| FactSales[product_id] | DimProduct[product_id] | Many-to-one | Single |
| FactSales[region_key] | DimRegion[region_key] | Many-to-one | Single |
| FactSales[order_date] | DimDate[Date] | Many-to-one | Single |
| FactInventory[product_id] | DimProduct[product_id] | Many-to-one | Single |
| FactInventory[region_key] | DimRegion[region_key] | Many-to-one | Single |

Delete any relationship Power BI auto-detected that is not in this list. Facts never connect directly to each other — they share dimensions. That is the star schema.

## 4. DimDate table in DAX

**Modeling → New table**, paste:

```DAX
DimDate =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2025, 1, 1 ), DATE ( 2025, 12, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Quarter", "Q" & QUARTER ( [Date] ),
    "Month Number", MONTH ( [Date] ),
    "Month", FORMAT ( [Date], "mmm" ),
    "Year Month", FORMAT ( [Date], "yyyy-mm" ),
    "Weekday", FORMAT ( [Date], "ddd" )
)
```

Then:
1. Select the table → **Table tools → Mark as date table** → choose `Date`.
2. Select the `Month` column → **Sort by column** → `Month Number` (otherwise months sort alphabetically: Apr, Aug, Dec…).
3. Create the relationship `FactSales[order_date]` → `DimDate[Date]` (step 3).

## 5. DAX measures

Create a blank table to hold measures: **Home → Enter data** → name it `_Measures` → Load. Then select it and use **New measure** for each:

```DAX
Total Revenue = SUM ( FactSales[revenue] )
```
Adds up revenue of every visible sale. "Visible" = what is left after slicers and filters.

```DAX
Total Cost = SUM ( FactSales[cost] )
```
Cost of goods sold for the visible sales.

```DAX
Gross Profit = [Total Revenue] - [Total Cost]
```
Re-uses the two measures above. Should equal `SUM(FactSales[gross_profit])`.

```DAX
Gross Margin % = DIVIDE ( [Gross Profit], [Total Revenue] )
```
`DIVIDE` returns BLANK instead of an error when revenue is 0. Format as Percentage, 1 decimal.

```DAX
Orders = DISTINCTCOUNT ( FactSales[order_id] )
```
Number of unique orders.

```DAX
Units Sold = SUM ( FactSales[quantity] )
```

```DAX
Average Order Value = DIVIDE ( [Total Revenue], [Orders] )
```
AOV = revenue per order.

```DAX
Revenue Previous Month =
CALCULATE ( [Total Revenue], DATEADD ( DimDate[Date], -1, MONTH ) )
```
`CALCULATE` re-runs `[Total Revenue]` with a changed filter; `DATEADD` shifts the date filter back one month. Needs the marked date table.

```DAX
Revenue MoM % =
DIVIDE ( [Total Revenue] - [Revenue Previous Month], [Revenue Previous Month] )
```
Month-over-month growth. January is BLANK because there is no December 2024 in the data. Format as Percentage.

```DAX
Revenue YTD = TOTALYTD ( [Total Revenue], DimDate[Date] )
```
Running total from 1 January to the current date in the visual (same idea as SQL query Q8).

```DAX
Online Revenue = CALCULATE ( [Total Revenue], FactSales[channel] = "Online" )
```
`CALCULATE` with a filter argument: only Online sales, whatever other filters are active.

```DAX
Channel Share % =
DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], ALL ( FactSales[channel] ) ) )
```
`ALL` removes the channel filter in the denominator, so each channel is divided by the total of all channels (same as SQL Q4).

```DAX
Reorder Alerts = CALCULATE ( COUNTROWS ( FactInventory ), FactInventory[stock_status] = "Reorder" )
```

```DAX
Overstock Alerts = CALCULATE ( COUNTROWS ( FactInventory ), FactInventory[stock_status] = "Overstock" )
```

```DAX
Inventory Value = SUM ( FactInventory[inventory_value] )
```

Format money measures as Currency → ₹ (Indian rupee), 0 decimals.

## 6. Report pages

**Page 1 – Executive Overview**
- Cards: Total Revenue, Gross Profit, Gross Margin %, Orders, Average Order Value.
- Line chart: X = DimDate[Year Month], Y = Total Revenue.
- Column chart: X = DimDate[Year Month], Y = Revenue MoM %.
- Clustered bar: DimRegion[region_name] by Total Revenue and Gross Profit.
- Donut: FactSales[channel] by Total Revenue.

**Page 2 – Product Performance**
- Bar chart: top 10 DimProduct[product_name] by Total Revenue (Filters pane → Top N = 10).
- Table: category, product_name, Total Revenue, Gross Profit, Gross Margin %, Units Sold.
- Matrix: rows = region_name, columns = category, values = Total Revenue.

**Page 3 – Inventory Actions**
- Cards: Reorder Alerts, Overstock Alerts, Inventory Value.
- Table: region_name, product_name, on_hand_units, reorder_point, target_stock, stock_status, inventory_value; conditional formatting on stock_status (red Reorder, amber Overstock).

**Page 4 – About / Data quality**
- Text box: "Synthetic data generated with seed 42. Returns (40 rows, 87 units) are excluded from revenue." Paste the issue table from `reports/data_quality_report.md`.

## 7. Slicers

Add on pages 1–2 (and sync them with **View → Sync slicers**):
- DimDate[Date] (Between style) or DimDate[Year Month]
- DimRegion[region_name]
- DimProduct[category]
- FactSales[channel]

On page 3 use only Region and Category (inventory has no order date or channel).

## 8. Reconciliation checklist (Power BI vs SQL)

With **no slicers applied**, the numbers must match `reports/sql_results.md`:

| Check | Expected (synthetic) | Source query | ✓ |
|---|---:|---|---|
| Total Revenue | ₹37,607,486.05 | Q8 last running total | ☐ |
| Gross Profit | ₹12,959,219.05 | sum of Q3 gross_profit | ☐ |
| Gross Margin % | 34.5% | – | ☐ |
| Orders | 5,948 | Q5 "All channels" | ☐ |
| Average Order Value | ₹6,322.71 | Q5 "All channels" | ☐ |
| Revenue, Dec 2025 | ₹4,380,829.10 | Q1 | ☐ |
| Revenue MoM %, Oct 2025 | 19.4% | Q1 | ☐ |
| Online share | 45.4% | Q4 | ☐ |
| Home gross margin % | 38.3% | Q3 | ☐ |
| Reorder / Healthy / Overstock rows | 15 / 37 / 28 | Q10 | ☐ |
| Inventory Value | ₹7,027,455 | sum of Q10 | ☐ |
| Duplicate order_ids | 0 | Q7 (no rows) | ☐ |

If a number does not match, check in this order: (1) a slicer or page filter is still active, (2) a column type is wrong (text instead of number), (3) a relationship is missing or points the wrong way, (4) you imported `dim_date.csv` **and** built DimDate in DAX.

If you regenerate the data with a different seed, re-run `python src/run_sql.py` and compare against the new results instead of the numbers above.
