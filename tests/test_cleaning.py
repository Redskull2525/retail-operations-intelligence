"""The cleaned data must be safe to report on."""

import pandas as pd

from src import generate_data as g
from src import pipeline


def test_row_counts_add_up(built):
    raw_rows = g.N_SALES_ROWS + g.N_DUPLICATES
    expected_clean = raw_rows - g.N_DUPLICATES - g.N_BAD_DATES - g.N_RETURNS
    assert len(built["tables"]["fact_sales"]) == expected_clean
    assert len(built["returns"]) == g.N_RETURNS


def test_no_duplicates(built):
    fact = built["tables"]["fact_sales"]
    assert not fact.duplicated().any()
    assert not fact["order_id"].duplicated().any()


def test_no_negative_quantity_or_revenue(built):
    fact = built["tables"]["fact_sales"]
    assert (fact["quantity"] > 0).all()
    assert (fact["revenue"] >= 0).all()


def test_all_dates_in_2025(built):
    dates = pd.to_datetime(built["tables"]["fact_sales"]["order_date"])
    assert dates.min() >= pd.Timestamp("2025-01-01")
    assert dates.max() <= pd.Timestamp("2025-12-31")


def test_text_is_standardised(built):
    clean = built["clean_sales"]
    assert set(clean["region"]) <= {"West", "North", "South", "East", "Unknown"}
    assert set(clean["channel"]) == {"Online", "Retail Store", "Marketplace"}
    assert (clean["region"] == "Unknown").sum() == g.N_MISSING_REGION


def test_standardize_text_examples():
    regions = ["West", "North", "South", "East"]
    assert pipeline.standardize_text(" west", regions, "Unknown") == "West"
    assert pipeline.standardize_text("NORTH ", regions, "Unknown") == "North"
    assert pipeline.standardize_text(None, regions, "Unknown") == "Unknown"
    assert pipeline.standardize_text("Mars", regions, "Unknown") == "Unknown"


def test_every_fact_row_has_valid_keys(built):
    tables = built["tables"]
    fact = tables["fact_sales"]
    assert fact["product_id"].isin(tables["dim_product"]["product_id"]).all()
    assert fact["region_key"].isin(tables["dim_region"]["region_key"]).all()
    assert fact["date_key"].isin(tables["dim_date"]["date_key"]).all()


def test_all_three_stock_statuses_occur(built):
    statuses = set(built["tables"]["fact_inventory"]["stock_status"])
    assert statuses == {"Reorder", "Healthy", "Overstock"}


def test_post_clean_checks_all_pass(built):
    assert all(built["checks"].values())
    assert "FAIL" not in built["report_path"].read_text(encoding="utf-8")
