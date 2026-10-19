-- schema.sql
-- Star schema for the SYNTHETIC retail warehouse (data/warehouse.db, SQLite).
--
--   dim_product   one row per product
--   dim_region    one row per region (includes 'Unknown' for missing regions)
--   dim_date      one row per calendar day in 2025
--   fact_sales    one row per completed order line (returns are excluded)
--   fact_inventory one row per product per region on the snapshot date
--
-- The pipeline drops and recreates these tables every run, so it is safe to re-run.

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS fact_inventory;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_product (
    product_id     TEXT PRIMARY KEY,      -- e.g. 'P001'
    product_name   TEXT NOT NULL,
    category       TEXT NOT NULL,
    unit_cost      REAL NOT NULL,         -- INR
    unit_price     REAL NOT NULL,         -- INR (list price)
    reorder_point  INTEGER NOT NULL,      -- reorder when stock falls to this level
    target_stock   INTEGER NOT NULL       -- ideal stock level
);

CREATE TABLE dim_region (
    region_key   INTEGER PRIMARY KEY,     -- surrogate key 1, 2, 3 ...
    region_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,     -- YYYYMMDD, e.g. 20250131
    full_date    TEXT NOT NULL,           -- 'YYYY-MM-DD'
    year         INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    month_name   TEXT NOT NULL,
    year_month   TEXT NOT NULL,           -- 'YYYY-MM', handy for grouping
    day_of_week  TEXT NOT NULL
);

CREATE TABLE fact_sales (
    order_id      TEXT PRIMARY KEY,       -- one product per order in this dataset
    date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    order_date    TEXT NOT NULL,
    product_id    TEXT NOT NULL REFERENCES dim_product(product_id),
    region_key    INTEGER NOT NULL REFERENCES dim_region(region_key),
    channel       TEXT NOT NULL,          -- Online / Retail Store / Marketplace
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL NOT NULL,
    discount_pct  REAL NOT NULL,
    revenue       REAL NOT NULL CHECK (revenue >= 0),   -- quantity * unit_price * (1 - discount_pct)
    cost          REAL NOT NULL,                        -- quantity * unit_cost
    gross_profit  REAL NOT NULL                         -- revenue - cost
);

CREATE TABLE fact_inventory (
    snapshot_date_key  INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_id         TEXT NOT NULL REFERENCES dim_product(product_id),
    region_key         INTEGER NOT NULL REFERENCES dim_region(region_key),
    on_hand_units      INTEGER NOT NULL,
    inventory_value    REAL NOT NULL,     -- on_hand_units * unit_cost
    stock_status       TEXT NOT NULL,     -- Reorder / Healthy / Overstock
    PRIMARY KEY (snapshot_date_key, product_id, region_key)
);
