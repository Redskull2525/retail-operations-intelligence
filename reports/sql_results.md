# SQL Results

> Output of `python src/run_sql.py` on the **synthetic** warehouse. Not real business data.

## q01_monthly_revenue_mom

**Q1. What is revenue per month, and how much did it grow vs the previous month?**

| year_month | revenue | previous_month_revenue | mom_growth_pct |
|---|---|---|---|
| 2025-01 | 2,630,075.25 |  |  |
| 2025-02 | 2,095,186.25 | 2,630,075.25 | -20.30 |
| 2025-03 | 2,738,424.80 | 2,095,186.25 | 30.70 |
| 2025-04 | 2,820,844.65 | 2,738,424.80 | 3.00 |
| 2025-05 | 2,728,847.95 | 2,820,844.65 | -3.30 |
| 2025-06 | 2,772,608.85 | 2,728,847.95 | 1.60 |
| 2025-07 | 2,750,605.65 | 2,772,608.85 | -0.80 |
| 2025-08 | 3,184,227.25 | 2,750,605.65 | 15.80 |
| 2025-09 | 3,344,105.65 | 3,184,227.25 | 5.00 |
| 2025-10 | 3,993,500.60 | 3,344,105.65 | 19.40 |
| 2025-11 | 4,168,230.05 | 3,993,500.60 | 4.40 |
| 2025-12 | 4,380,829.10 | 4,168,230.05 | 5.10 |

## q02_top5_products_per_region

**Q2. Which 5 products bring the most revenue in each region?**

| region_name | revenue_rank | product_name | revenue |
|---|---|---|---|
| East | 1 | Air Purifier | 723,478.00 |
| East | 2 | Monitor Stand | 708,805.50 |
| East | 3 | Travel Mug | 704,585.40 |
| East | 4 | Notebook Pack | 533,065.00 |
| East | 5 | Paper Ream | 398,410.65 |
| North | 1 | Monitor Stand | 1,073,061.60 |
| North | 2 | Air Purifier | 1,010,352.00 |
| North | 3 | Travel Mug | 822,738.00 |
| North | 4 | USB-C Hub | 711,694.80 |
| North | 5 | Notebook Pack | 661,095.00 |
| South | 1 | Travel Mug | 892,639.80 |
| South | 2 | Monitor Stand | 850,142.80 |
| South | 3 | Air Purifier | 828,940.00 |
| South | 4 | Notebook Pack | 687,497.50 |
| South | 5 | USB-C Hub | 600,718.05 |
| West | 1 | Monitor Stand | 1,347,048.30 |
| West | 2 | Air Purifier | 1,160,950.00 |
| West | 3 | Travel Mug | 928,931.00 |
| West | 4 | USB-C Hub | 910,009.35 |
| West | 5 | Desk Lamp | 825,694.60 |

## q03_gross_margin_by_category

**Q3. Which category is most profitable as a % of revenue?**

| category | revenue | gross_profit | gross_margin_pct |
|---|---|---|---|
| Home | 8,868,535.60 | 3,399,797.60 | 38.30 |
| Electronics | 9,006,702.65 | 3,100,673.65 | 34.40 |
| Office | 9,844,861.90 | 3,274,328.90 | 33.30 |
| Lifestyle | 9,887,385.90 | 3,184,418.90 | 32.20 |

## q04_channel_mix

**Q4. What share of revenue comes from each sales channel?**

| channel | orders | revenue | revenue_share_pct |
|---|---|---|---|
| Online | 2731 | 17,071,722.25 | 45.40 |
| Retail Store | 2100 | 13,506,075.20 | 35.90 |
| Marketplace | 1117 | 7,029,688.60 | 18.70 |

## q05_average_order_value

**Q5. What is the average order value (AOV) overall and per channel?**

| channel | orders | average_order_value |
|---|---|---|
| All channels | 5948 | 6,322.71 |
| Marketplace | 1117 | 6,293.36 |
| Online | 2731 | 6,251.09 |
| Retail Store | 2100 | 6,431.46 |

## q06_reorder_alerts_last_90_days

**Q6. Which product-region stock levels need reordering, and how fast did they sell in the last 90 days of data? (fast sellers = order first)**

| region_name | product_name | on_hand_units | reorder_point | target_stock | units_to_order | units_last_90_days |
|---|---|---|---|---|---|---|
| West | Backpack | 15 | 24 | 96 | 81 | 103 |
| West | Webcam | 14 | 31 | 81 | 67 | 94 |
| West | Air Purifier | 20 | 27 | 104 | 84 | 89 |
| South | Keyboard | 11 | 20 | 104 | 93 | 85 |
| North | Travel Mug | 3 | 22 | 94 | 91 | 84 |
| North | Bluetooth Speaker | 28 | 34 | 100 | 72 | 83 |
| North | USB-C Hub | 12 | 16 | 56 | 44 | 81 |
| South | Wireless Mouse | 20 | 29 | 80 | 60 | 74 |
| North | Air Purifier | 15 | 27 | 104 | 89 | 69 |
| North | Desk Lamp | 17 | 24 | 81 | 64 | 69 |
| South | USB-C Hub | 1 | 16 | 56 | 55 | 68 |
| South | Office Chair | 18 | 29 | 97 | 79 | 61 |
| South | Desk Lamp | 4 | 24 | 81 | 77 | 49 |
| South | Backpack | 0 | 24 | 96 | 96 | 38 |
| East | Desk Lamp | 13 | 24 | 81 | 68 | 37 |

## q07_duplicate_order_check

**Q7. Data-quality check: is any order_id loaded more than once?**

_(no rows returned)_

## q08_running_total_revenue

**Q8. Cumulative (year-to-date) revenue by month.**

| year_month | revenue | running_total_revenue |
|---|---|---|
| 2025-01 | 2,630,075.25 | 2,630,075.25 |
| 2025-02 | 2,095,186.25 | 4,725,261.50 |
| 2025-03 | 2,738,424.80 | 7,463,686.30 |
| 2025-04 | 2,820,844.65 | 10,284,530.95 |
| 2025-05 | 2,728,847.95 | 13,013,378.90 |
| 2025-06 | 2,772,608.85 | 15,785,987.75 |
| 2025-07 | 2,750,605.65 | 18,536,593.40 |
| 2025-08 | 3,184,227.25 | 21,720,820.65 |
| 2025-09 | 3,344,105.65 | 25,064,926.30 |
| 2025-10 | 3,993,500.60 | 29,058,426.90 |
| 2025-11 | 4,168,230.05 | 33,226,656.95 |
| 2025-12 | 4,380,829.10 | 37,607,486.05 |

## q09_region_performance

**Q9. Revenue, profit, orders and margin per region (incl. 'Unknown').**

| region_name | orders | revenue | gross_profit | gross_margin_pct |
|---|---|---|---|---|
| West | 1901 | 11,854,111.10 | 4,090,305.10 | 34.50 |
| North | 1504 | 9,829,235.95 | 3,377,646.95 | 34.40 |
| South | 1431 | 8,980,680.05 | 3,112,659.05 | 34.70 |
| East | 1097 | 6,845,100.40 | 2,346,011.40 | 34.30 |
| Unknown | 15 | 98,358.55 | 32,596.55 | 33.10 |

## q10_inventory_status_summary

**Q10. How many product-region rows are Reorder / Healthy / Overstock, and how much stock value (at cost) sits in each group?**

| stock_status | product_region_rows | units_on_hand | inventory_value_at_cost |
|---|---|---|---|
| Healthy | 37 | 2077 | 2,852,287.00 |
| Overstock | 28 | 3000 | 3,888,594.00 |
| Reorder | 15 | 191 | 286,574.00 |
