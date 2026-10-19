-- business_questions.sql
-- Business questions answered with SQL on the SYNTHETIC warehouse (data/warehouse.db).
--
-- Each query starts with a line "-- name: <short_name>".
-- src/run_sql.py splits this file on those lines and runs every query.
-- Money values are in INR. Returns are NOT in fact_sales (see README).


-- name: q01_monthly_revenue_mom
-- Q1. What is revenue per month, and how much did it grow vs the previous month?
-- LAG() looks at the previous row (previous month) inside the window.
WITH monthly AS (
    SELECT d.year_month,
           SUM(f.revenue) AS revenue
    FROM fact_sales AS f
    JOIN dim_date AS d ON d.date_key = f.date_key
    GROUP BY d.year_month
)
SELECT year_month,
       ROUND(revenue, 2)                                   AS revenue,
       ROUND(LAG(revenue) OVER (ORDER BY year_month), 2)   AS previous_month_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY year_month))
             / LAG(revenue) OVER (ORDER BY year_month), 1) AS mom_growth_pct
FROM monthly
ORDER BY year_month;


-- name: q02_top5_products_per_region
-- Q2. Which 5 products bring the most revenue in each region?
-- Step 1 (CTE) adds up revenue per region + product.
-- Step 2 RANK() numbers products inside each region (PARTITION BY region).
WITH product_region AS (
    SELECT r.region_name,
           p.product_name,
           SUM(f.revenue) AS revenue
    FROM fact_sales AS f
    JOIN dim_region  AS r ON r.region_key = f.region_key
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE r.region_name <> 'Unknown'
    GROUP BY r.region_name, p.product_name
),
ranked AS (
    SELECT region_name,
           product_name,
           revenue,
           RANK() OVER (PARTITION BY region_name ORDER BY revenue DESC) AS revenue_rank
    FROM product_region
)
SELECT region_name, revenue_rank, product_name, ROUND(revenue, 2) AS revenue
FROM ranked
WHERE revenue_rank <= 5
ORDER BY region_name, revenue_rank;


-- name: q03_gross_margin_by_category
-- Q3. Which category is most profitable as a % of revenue?
SELECT p.category,
       ROUND(SUM(f.revenue), 2)                                  AS revenue,
       ROUND(SUM(f.gross_profit), 2)                             AS gross_profit,
       ROUND(100.0 * SUM(f.gross_profit) / SUM(f.revenue), 1)    AS gross_margin_pct
FROM fact_sales AS f
JOIN dim_product AS p ON p.product_id = f.product_id
GROUP BY p.category
ORDER BY gross_margin_pct DESC;


-- name: q04_channel_mix
-- Q4. What share of revenue comes from each sales channel?
-- SUM(...) OVER () with an empty window = grand total across all rows.
SELECT channel,
       COUNT(*)                                                   AS orders,
       ROUND(SUM(revenue), 2)                                     AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_share_pct
FROM fact_sales
GROUP BY channel
ORDER BY revenue DESC;


-- name: q05_average_order_value
-- Q5. What is the average order value (AOV) overall and per channel?
-- AOV = total revenue / number of distinct orders.
SELECT 'All channels'                                       AS channel,
       COUNT(DISTINCT order_id)                             AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)    AS average_order_value
FROM fact_sales
UNION ALL
SELECT channel,
       COUNT(DISTINCT order_id),
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)
FROM fact_sales
GROUP BY channel;


-- name: q06_reorder_alerts_last_90_days
-- Q6. Which product-region stock levels need reordering, and how fast did
--     they sell in the last 90 days of data? (fast sellers = order first)
-- The 90-day window ends on the last order date in the data (2025-12-31).
WITH recent_sales AS (
    SELECT product_id,
           region_key,
           SUM(quantity) AS units_last_90_days
    FROM fact_sales
    WHERE order_date > DATE((SELECT MAX(order_date) FROM fact_sales), '-90 days')
    GROUP BY product_id, region_key
)
SELECT r.region_name,
       p.product_name,
       i.on_hand_units,
       p.reorder_point,
       p.target_stock,
       p.target_stock - i.on_hand_units         AS units_to_order,
       COALESCE(s.units_last_90_days, 0)        AS units_last_90_days
FROM fact_inventory AS i
JOIN dim_product AS p ON p.product_id = i.product_id
JOIN dim_region  AS r ON r.region_key = i.region_key
LEFT JOIN recent_sales AS s
       ON s.product_id = i.product_id AND s.region_key = i.region_key
WHERE i.stock_status = 'Reorder'
ORDER BY units_last_90_days DESC, i.on_hand_units ASC;


-- name: q07_duplicate_order_check
-- Q7. Data-quality check: is any order_id loaded more than once?
-- Expected result: zero rows (the pipeline removed duplicates).
SELECT order_id, COUNT(*) AS times_loaded
FROM fact_sales
GROUP BY order_id
HAVING COUNT(*) > 1;


-- name: q08_running_total_revenue
-- Q8. Cumulative (year-to-date) revenue by month.
-- SUM() OVER (ORDER BY ...) keeps adding each month to the previous total.
WITH monthly AS (
    SELECT d.year_month, SUM(f.revenue) AS revenue
    FROM fact_sales AS f
    JOIN dim_date AS d ON d.date_key = f.date_key
    GROUP BY d.year_month
)
SELECT year_month,
       ROUND(revenue, 2)                                  AS revenue,
       ROUND(SUM(revenue) OVER (ORDER BY year_month), 2)  AS running_total_revenue
FROM monthly
ORDER BY year_month;


-- name: q09_region_performance
-- Q9. Revenue, profit, orders and margin per region (incl. 'Unknown').
SELECT r.region_name,
       COUNT(*)                                               AS orders,
       ROUND(SUM(f.revenue), 2)                               AS revenue,
       ROUND(SUM(f.gross_profit), 2)                          AS gross_profit,
       ROUND(100.0 * SUM(f.gross_profit) / SUM(f.revenue), 1) AS gross_margin_pct
FROM fact_sales AS f
JOIN dim_region AS r ON r.region_key = f.region_key
GROUP BY r.region_name
ORDER BY revenue DESC;


-- name: q10_inventory_status_summary
-- Q10. How many product-region rows are Reorder / Healthy / Overstock,
--      and how much stock value (at cost) sits in each group?
SELECT stock_status,
       COUNT(*)                        AS product_region_rows,
       SUM(on_hand_units)              AS units_on_hand,
       ROUND(SUM(inventory_value), 2)  AS inventory_value_at_cost
FROM fact_inventory
GROUP BY stock_status
ORDER BY product_region_rows DESC;
