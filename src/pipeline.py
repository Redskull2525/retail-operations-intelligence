"""
pipeline.py
-----------
A small ETL pipeline:  Extract -> Validate -> Clean -> Load

    Extract  : read the three raw CSV files from data/raw/
    Validate : COUNT every data-quality problem (nothing is changed yet)
    Clean    : fix or remove the problems, one clear rule at a time
    Load     : write a SQLite star schema (data/warehouse.db) and
               Power-BI-ready CSV files (data/processed/)

It also writes reports/data_quality_report.md so anyone can see what was
found and what was done about it.

Returns decision
----------------
Rows with a NEGATIVE quantity are product returns. In this dataset they are
not linked to the original order, so we cannot safely subtract them from the
right sale. We therefore:
    * EXCLUDE them from fact_sales (revenue KPIs = completed sales only), and
    * SAVE them to data/processed/returns_excluded.csv so they are not lost
      and can be analysed separately (return count and units).

Run:  python src/pipeline.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Allow "python src/pipeline.py" as well as "import src.pipeline"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import metrics  # noqa: E402

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DB_PATH = PROJECT_ROOT / "data" / "warehouse.db"
REPORT_PATH = PROJECT_ROOT / "reports" / "data_quality_report.md"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"

VALID_REGIONS = ["West", "North", "South", "East"]
VALID_CHANNELS = ["Online", "Retail Store", "Marketplace"]
UNKNOWN_REGION = "Unknown"
VALID_YEAR = 2025


# ---------------------------------------------------------------------------
# 1. EXTRACT
# ---------------------------------------------------------------------------

def extract(raw_dir=RAW_DIR):
    """Read the raw CSV files. Everything is read as text-friendly types;
    dates are parsed later so a bad date cannot crash the read."""
    raw_dir = Path(raw_dir)
    sales = pd.read_csv(raw_dir / "sales_transactions_raw.csv")
    products = pd.read_csv(raw_dir / "product_catalog.csv")
    inventory = pd.read_csv(raw_dir / "inventory_snapshot.csv")
    return sales, products, inventory


# ---------------------------------------------------------------------------
# 2. VALIDATE  (count problems, change nothing)
# ---------------------------------------------------------------------------

def validate_sales(sales, products):
    """Return a dictionary: check name -> number of rows with that problem."""
    issues = {}

    # Exact duplicate rows (every column identical to an earlier row)
    issues["exact_duplicate_rows"] = int(sales.duplicated().sum())

    # Same order_id used for DIFFERENT content (after removing exact copies)
    without_exact_copies = sales.drop_duplicates()
    issues["conflicting_order_ids"] = int(without_exact_copies["order_id"].duplicated().sum())

    # Region blank or missing
    region_text = sales["region"].astype("string").str.strip()
    region_missing = region_text.isna() | (region_text == "")
    issues["missing_region"] = int(region_missing.sum())

    # Region present but not written exactly like 'West', 'North' ...
    region_not_standard = ~region_missing & ~sales["region"].isin(VALID_REGIONS)
    issues["non_standard_region_text"] = int(region_not_standard.sum())

    # Channel not written exactly like 'Online', 'Retail Store', 'Marketplace'
    issues["non_standard_channel_text"] = int((~sales["channel"].isin(VALID_CHANNELS)).sum())

    # Quantity checks
    issues["negative_quantity_returns"] = int((sales["quantity"] < 0).sum())
    issues["zero_quantity"] = int((sales["quantity"] == 0).sum())

    # Dates that cannot be read, or that fall outside the year 2025
    parsed_dates = pd.to_datetime(sales["order_date"], errors="coerce")
    bad_date = parsed_dates.isna() | (parsed_dates.dt.year != VALID_YEAR)
    issues["date_outside_2025_or_invalid"] = int(bad_date.sum())

    # Product id that is not in the catalog
    issues["unknown_product_id"] = int((~sales["product_id"].isin(products["product_id"])).sum())

    # Discount must be between 0% and 90%
    bad_discount = (sales["discount_pct"] < 0) | (sales["discount_pct"] > 0.9)
    issues["invalid_discount"] = int(bad_discount.sum())

    return issues


def validate_inventory(inventory, products):
    """Simple checks on the inventory snapshot."""
    issues = {}
    issues["inventory_negative_on_hand"] = int((inventory["on_hand_units"] < 0).sum())
    issues["inventory_unknown_product_id"] = int(
        (~inventory["product_id"].isin(products["product_id"])).sum()
    )
    issues["inventory_duplicate_product_region"] = int(
        inventory.duplicated(subset=["product_id", "region"]).sum()
    )
    return issues


# ---------------------------------------------------------------------------
# 3. CLEAN
# ---------------------------------------------------------------------------

def standardize_text(value, valid_values, default):
    """Turn ' west' / 'WEST ' / 'west' into 'West'.

    We strip spaces, compare in lower case, and return the official spelling.
    Anything blank or unrecognised becomes `default`.
    """
    if pd.isna(value):
        return default
    cleaned = str(value).strip().lower()
    for valid in valid_values:
        if cleaned == valid.lower():
            return valid
    return default


def clean_sales(sales, products):
    """Apply the cleaning rules in a fixed order.

    Returns (clean_sales, returns, steps) where `steps` is a list of
    dictionaries describing each step (used in the report).
    """
    steps = []
    data = sales.copy()

    # Step 1: remove exact duplicate rows
    before = len(data)
    data = data.drop_duplicates().reset_index(drop=True)
    steps.append({"step": "Remove exact duplicate rows", "rows_before": before, "rows_after": len(data)})

    # Step 2: standardise region and channel text (row count does not change)
    before = len(data)
    data["region"] = data["region"].apply(standardize_text, args=(VALID_REGIONS, UNKNOWN_REGION))
    data["channel"] = data["channel"].apply(standardize_text, args=(VALID_CHANNELS, "Unknown"))
    steps.append({"step": "Standardise region/channel text; blank region -> 'Unknown'",
                  "rows_before": before, "rows_after": len(data)})

    # Step 3: remove rows dated outside 2025 (they belong to another reporting year)
    before = len(data)
    data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce")
    in_2025 = data["order_date"].dt.year == VALID_YEAR
    data = data[in_2025].reset_index(drop=True)
    steps.append({"step": "Remove rows dated outside 2025", "rows_before": before, "rows_after": len(data)})

    # Step 4: separate returns (negative quantity) from completed sales
    before = len(data)
    is_return = data["quantity"] < 0
    returns = data[is_return].reset_index(drop=True)
    data = data[~is_return].reset_index(drop=True)
    steps.append({"step": "Move returns (negative quantity) to returns_excluded.csv",
                  "rows_before": before, "rows_after": len(data)})

    # Step 5: remove anything else that cannot be used (zero quantity, unknown product)
    before = len(data)
    usable = (data["quantity"] > 0) & data["product_id"].isin(products["product_id"])
    data = data[usable].reset_index(drop=True)
    steps.append({"step": "Remove zero-quantity / unknown-product rows",
                  "rows_before": before, "rows_after": len(data)})

    # Step 6: calculate money columns using the catalog cost
    data = data.merge(products[["product_id", "unit_cost"]], on="product_id", how="left")
    data["revenue"] = metrics.calculate_revenue(data["quantity"], data["unit_price"], data["discount_pct"])
    data["cost"] = (data["quantity"] * data["unit_cost"]).round(2)
    data["gross_profit"] = (data["revenue"] - data["cost"]).round(2)
    data = data.drop(columns=["unit_cost"])

    return data, returns, steps


def check_clean_sales(clean):
    """Post-clean checks. Returns a dict of check -> True/False.
    The pipeline stops with an error if any check fails."""
    checks = {
        "no duplicate order_id": not clean["order_id"].duplicated().any(),
        "all quantities > 0": bool((clean["quantity"] > 0).all()),
        "no negative revenue": bool((clean["revenue"] >= 0).all()),
        "all dates in 2025": bool((clean["order_date"].dt.year == VALID_YEAR).all()),
        "regions are standard or 'Unknown'": bool(clean["region"].isin(VALID_REGIONS + [UNKNOWN_REGION]).all()),
        "channels are standard": bool(clean["channel"].isin(VALID_CHANNELS).all()),
    }
    return checks


# ---------------------------------------------------------------------------
# 4. BUILD STAR SCHEMA TABLES
# ---------------------------------------------------------------------------

def build_dim_date(year=VALID_YEAR):
    """One row per day of the year."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    dim_date = pd.DataFrame({
        "date_key": days.strftime("%Y%m%d").astype(int),
        "full_date": days.strftime("%Y-%m-%d"),
        "year": days.year,
        "quarter": days.quarter,
        "month": days.month,
        "month_name": days.strftime("%b"),
        "year_month": days.strftime("%Y-%m"),
        "day_of_week": days.strftime("%a"),
    })
    return dim_date


def build_dim_region():
    """Fixed list of regions with integer surrogate keys."""
    names = VALID_REGIONS + [UNKNOWN_REGION]
    return pd.DataFrame({"region_key": range(1, len(names) + 1), "region_name": names})


def build_fact_sales(clean, dim_region):
    """Replace region text with region_key and add date_key."""
    fact = clean.merge(dim_region, left_on="region", right_on="region_name", how="left")
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact["order_date"] = fact["order_date"].dt.strftime("%Y-%m-%d")
    columns = ["order_id", "date_key", "order_date", "product_id", "region_key", "channel",
               "quantity", "unit_price", "discount_pct", "revenue", "cost", "gross_profit"]
    return fact[columns].sort_values("order_id").reset_index(drop=True)


def build_fact_inventory(inventory, products, dim_region):
    """Add stock status and value to each product-region stock row."""
    inv = inventory.merge(products, on="product_id", how="left")
    inv = inv.merge(dim_region, left_on="region", right_on="region_name", how="left")
    statuses = []
    for _, row in inv.iterrows():
        statuses.append(metrics.stock_status(row["on_hand_units"], row["reorder_point"], row["target_stock"]))
    inv["stock_status"] = statuses
    inv["inventory_value"] = inv["on_hand_units"] * inv["unit_cost"]
    inv["snapshot_date_key"] = pd.to_datetime(inv["snapshot_date"]).dt.strftime("%Y%m%d").astype(int)
    columns = ["snapshot_date_key", "product_id", "region_key", "on_hand_units",
               "inventory_value", "stock_status"]
    return inv[columns]


# ---------------------------------------------------------------------------
# 5. LOAD
# ---------------------------------------------------------------------------

def load_to_sqlite(tables, db_path=DB_PATH, schema_path=SCHEMA_PATH):
    """Create the schema from sql/schema.sql, then insert each DataFrame."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
        # Insert dimensions first, then facts (facts refer to dimensions)
        for name in ["dim_product", "dim_region", "dim_date", "fact_sales", "fact_inventory"]:
            tables[name].to_sql(name, connection, if_exists="append", index=False)
        connection.commit()
    finally:
        connection.close()


def save_processed_csvs(tables, returns, processed_dir=PROCESSED_DIR):
    """Write one CSV per table for Power BI and the Streamlit app."""
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(processed_dir / f"{name}.csv", index=False)
    returns_out = returns.copy()
    returns_out["order_date"] = returns_out["order_date"].dt.strftime("%Y-%m-%d")
    returns_out.to_csv(processed_dir / "returns_excluded.csv", index=False)


# ---------------------------------------------------------------------------
# 6. REPORT
# ---------------------------------------------------------------------------

HANDLING = {
    "exact_duplicate_rows": "Removed (kept the first copy)",
    "conflicting_order_ids": "Would stop for review (none expected)",
    "missing_region": "Kept the sale; region set to 'Unknown' so revenue is not lost",
    "non_standard_region_text": "Trimmed spaces and fixed capitalisation",
    "non_standard_channel_text": "Trimmed spaces and fixed capitalisation",
    "negative_quantity_returns": "Excluded from fact_sales; saved to returns_excluded.csv",
    "zero_quantity": "Removed",
    "date_outside_2025_or_invalid": "Removed (outside the 2025 reporting year)",
    "unknown_product_id": "Removed",
    "invalid_discount": "Would stop for review (none expected)",
    "inventory_negative_on_hand": "Would stop for review (none expected)",
    "inventory_unknown_product_id": "Would stop for review (none expected)",
    "inventory_duplicate_product_region": "Would stop for review (none expected)",
}


def build_report(raw_rows, issues, steps, checks, fact_sales, returns, fact_inventory):
    """Create the Markdown text of the data-quality report."""
    lines = []
    lines.append("# Data Quality Report")
    lines.append("")
    lines.append("> All data is **synthetic** (generated by `src/generate_data.py`, seed 42). "
                 "The issues below were injected on purpose to demonstrate cleaning.")
    lines.append("")
    lines.append(f"- Raw sales rows read: **{raw_rows:,}**")
    lines.append(f"- Clean sales rows loaded to `fact_sales`: **{len(fact_sales):,}**")
    lines.append(f"- Returns kept aside in `returns_excluded.csv`: **{len(returns):,}** "
                 f"({int(-returns['quantity'].sum())} units)")
    lines.append(f"- Inventory rows loaded to `fact_inventory`: **{len(fact_inventory):,}**")
    lines.append("")
    lines.append("## 1. Issues found in the raw data")
    lines.append("")
    lines.append("| Check | Rows found | How it was handled |")
    lines.append("|---|---:|---|")
    for check, count in issues.items():
        handling = HANDLING.get(check, "") if count > 0 else "Passed - nothing to do"
        lines.append(f"| {check} | {count} | {handling} |")
    lines.append("")
    lines.append("## 2. Cleaning steps (row counts)")
    lines.append("")
    lines.append("| # | Step | Rows before | Rows after | Rows removed |")
    lines.append("|---:|---|---:|---:|---:|")
    for number, step in enumerate(steps, start=1):
        removed = step["rows_before"] - step["rows_after"]
        lines.append(f"| {number} | {step['step']} | {step['rows_before']:,} | {step['rows_after']:,} | {removed} |")
    lines.append("")
    lines.append("## 3. Checks on the cleaned data")
    lines.append("")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for check, passed in checks.items():
        lines.append(f"| {check} | {'PASS' if passed else 'FAIL'} |")
    lines.append("")
    status_counts = fact_inventory["stock_status"].value_counts()
    lines.append("## 4. Inventory stock status (snapshot 2025-12-31)")
    lines.append("")
    lines.append("| Status | Product-region rows |")
    lines.append("|---|---:|")
    for status in ["Reorder", "Healthy", "Overstock"]:
        lines.append(f"| {status} | {int(status_counts.get(status, 0))} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run_pipeline(raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR, db_path=DB_PATH,
                 report_path=REPORT_PATH, verbose=True):
    """Run every step and return a dictionary with the important outputs."""
    # Extract
    sales_raw, products, inventory_raw = extract(raw_dir)

    # Validate
    issues = validate_sales(sales_raw, products)
    issues.update(validate_inventory(inventory_raw, products))
    inventory_problems = (issues["inventory_negative_on_hand"] + issues["inventory_unknown_product_id"]
                          + issues["inventory_duplicate_product_region"])
    if inventory_problems > 0 or issues["conflicting_order_ids"] > 0:
        raise ValueError(f"Data needs manual review before loading: {issues}")

    # Clean
    clean, returns, steps = clean_sales(sales_raw, products)
    checks = check_clean_sales(clean)
    if not all(checks.values()):
        raise ValueError(f"Post-clean checks failed: {checks}")

    # Build star schema tables
    dim_region = build_dim_region()
    tables = {
        "dim_product": products,
        "dim_region": dim_region,
        "dim_date": build_dim_date(),
        "fact_sales": build_fact_sales(clean, dim_region),
        "fact_inventory": build_fact_inventory(inventory_raw, products, dim_region),
    }

    # Load
    load_to_sqlite(tables, db_path)
    save_processed_csvs(tables, returns, processed_dir)

    # Report
    report = build_report(len(sales_raw), issues, steps, checks,
                          tables["fact_sales"], returns, tables["fact_inventory"])
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    if verbose:
        print(report)
        print(f"\nWarehouse written to {db_path}")
        print(f"Processed CSVs written to {processed_dir}")

    return {"issues": issues, "steps": steps, "checks": checks,
            "clean_sales": clean, "returns": returns, "tables": tables}


if __name__ == "__main__":
    run_pipeline()
