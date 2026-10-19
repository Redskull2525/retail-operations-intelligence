"""Validation must find every issue that the generator injected on purpose."""

import pandas as pd

from src import generate_data as g
from src import pipeline


def test_each_injected_issue_is_detected(built):
    issues = built["issues"]
    assert issues["exact_duplicate_rows"] == g.N_DUPLICATES
    assert issues["missing_region"] == g.N_MISSING_REGION
    assert issues["non_standard_region_text"] == g.N_MESSY_REGION
    assert issues["non_standard_channel_text"] == g.N_MESSY_CHANNEL
    assert issues["negative_quantity_returns"] == g.N_RETURNS
    assert issues["date_outside_2025_or_invalid"] == g.N_BAD_DATES


def test_checks_that_should_find_nothing(built):
    issues = built["issues"]
    for check in ["conflicting_order_ids", "zero_quantity", "unknown_product_id",
                  "invalid_discount", "inventory_negative_on_hand",
                  "inventory_unknown_product_id", "inventory_duplicate_product_region"]:
        assert issues[check] == 0, check


def test_validation_on_a_tiny_hand_made_table():
    products = pd.DataFrame({"product_id": ["P001"]})
    sales = pd.DataFrame({
        "order_id":     ["O1", "O1", "O2", "O3", "O4"],
        "order_date":   ["2025-01-01", "2025-01-01", "2026-02-01", "2025-03-01", "not a date"],
        "region":       ["West", "West", None, " north", "East"],
        "channel":      ["Online", "Online", "ONLINE", "Online", "Online"],
        "product_id":   ["P001", "P001", "P001", "P999", "P001"],
        "quantity":     [1, 1, -2, 0, 3],
        "unit_price":   [100, 100, 100, 100, 100],
        "discount_pct": [0.0, 0.0, 0.0, 1.5, 0.0],
    })
    issues = pipeline.validate_sales(sales, products)
    assert issues["exact_duplicate_rows"] == 1
    assert issues["missing_region"] == 1
    assert issues["non_standard_region_text"] == 1
    assert issues["non_standard_channel_text"] == 1
    assert issues["negative_quantity_returns"] == 1
    assert issues["zero_quantity"] == 1
    assert issues["date_outside_2025_or_invalid"] == 2
    assert issues["unknown_product_id"] == 1
    assert issues["invalid_discount"] == 1


def test_generator_is_reproducible(tmp_path):
    g.generate(tmp_path / "a")
    g.generate(tmp_path / "b")
    for name in ["sales_transactions_raw.csv", "product_catalog.csv", "inventory_snapshot.csv"]:
        assert (tmp_path / "a" / name).read_text() == (tmp_path / "b" / name).read_text()
