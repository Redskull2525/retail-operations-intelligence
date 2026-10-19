"""KPI formulas checked against numbers worked out by hand."""

import math

import pandas as pd
import pytest

from src import metrics


@pytest.fixture
def small_sales():
    # 3 order lines worked out by hand
    return pd.DataFrame({
        "order_id": ["O1", "O2", "O3"],
        "order_date": ["2025-01-10", "2025-01-20", "2025-02-05"],
        "quantity": [2, 1, 4],
        "revenue": [900.0, 300.0, 1200.0],
        "cost": [600.0, 200.0, 1000.0],
        "gross_profit": [300.0, 100.0, 200.0],
    })


def test_revenue_formula_single_values():
    # 2 units x Rs 500 with 10% discount = Rs 900
    assert metrics.calculate_revenue(2, 500, 0.10) == 900.0
    assert metrics.calculate_revenue(3, 199, 0.0) == 597.0


def test_revenue_formula_on_columns():
    result = metrics.calculate_revenue(pd.Series([1, 4]), pd.Series([1000, 250]), pd.Series([0.15, 0.05]))
    assert list(result) == [850.0, 950.0]


def test_revenue_matches_formula_in_built_data(built):
    fact = built["tables"]["fact_sales"]
    expected = (fact["quantity"] * fact["unit_price"] * (1 - fact["discount_pct"])).round(2)
    assert (fact["revenue"] - expected).abs().max() < 0.01
    assert ((fact["revenue"] - fact["cost"]) - fact["gross_profit"]).abs().max() < 0.01


def test_kpis(small_sales):
    assert metrics.total_revenue(small_sales) == 2400.0
    assert metrics.total_gross_profit(small_sales) == 600.0
    assert metrics.gross_margin_pct(small_sales) == 25.0
    assert metrics.order_count(small_sales) == 3
    assert metrics.units_sold(small_sales) == 7
    assert metrics.average_order_value(small_sales) == 800.0


def test_kpis_on_empty_data_do_not_crash(small_sales):
    empty = small_sales.iloc[0:0]
    assert metrics.gross_margin_pct(empty) == 0.0
    assert metrics.average_order_value(empty) == 0.0


def test_monthly_revenue_and_mom(small_sales):
    monthly = metrics.monthly_revenue(small_sales)
    assert list(monthly["month"]) == ["2025-01", "2025-02"]
    assert list(monthly["revenue"]) == [1200.0, 1200.0]
    assert math.isnan(monthly["mom_growth_pct"].iloc[0])
    assert monthly["mom_growth_pct"].iloc[1] == 0.0


def test_stock_status_rules():
    assert metrics.stock_status(10, reorder_point=20, target_stock=80) == "Reorder"
    assert metrics.stock_status(20, reorder_point=20, target_stock=80) == "Reorder"   # boundary
    assert metrics.stock_status(50, reorder_point=20, target_stock=80) == "Healthy"
    assert metrics.stock_status(80, reorder_point=20, target_stock=80) == "Healthy"   # boundary
    assert metrics.stock_status(81, reorder_point=20, target_stock=80) == "Overstock"


def test_recommended_action():
    assert metrics.recommended_action(5, 20, 80) == "Reorder 75 units"
    assert metrics.recommended_action(50, 20, 80) == "No immediate action"
    assert metrics.recommended_action(100, 20, 80).startswith("Review slow-moving stock")
