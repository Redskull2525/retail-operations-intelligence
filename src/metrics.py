"""
metrics.py
----------
All KPI (Key Performance Indicator) formulas live in ONE place.

The pipeline, the Streamlit app and the tests all import these functions,
so a formula only has to be written (and fixed) once.

Every function takes a pandas DataFrame of CLEAN sales lines with at least
these columns: order_id, order_date, quantity, revenue, cost, gross_profit.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Row-level formulas
# ---------------------------------------------------------------------------

def calculate_revenue(quantity, unit_price, discount_pct):
    """Revenue for one order line = quantity x unit price x (1 - discount).

    Example: 2 units x Rs 500 with 10% discount = 2 x 500 x 0.90 = Rs 900.00
    Works on single numbers or on whole pandas columns.
    """
    revenue = quantity * unit_price * (1 - discount_pct)
    return revenue.round(2) if hasattr(revenue, "round") else round(revenue, 2)


def stock_status(on_hand_units, reorder_point, target_stock):
    """Classify one product-region stock level.

    Reorder   : on hand is at or below the reorder point (risk of running out)
    Overstock : on hand is above the target stock level (cash tied up)
    Healthy   : everything in between
    """
    if on_hand_units <= reorder_point:
        return "Reorder"
    if on_hand_units > target_stock:
        return "Overstock"
    return "Healthy"


def recommended_action(on_hand_units, reorder_point, target_stock):
    """Plain-English next step for the inventory table."""
    status = stock_status(on_hand_units, reorder_point, target_stock)
    if status == "Reorder":
        units_to_order = target_stock - on_hand_units
        return f"Reorder {units_to_order} units"
    if status == "Overstock":
        extra_units = on_hand_units - target_stock
        return f"Review slow-moving stock ({extra_units} units above target)"
    return "No immediate action"


# ---------------------------------------------------------------------------
# KPI formulas (one number each)
# ---------------------------------------------------------------------------

def total_revenue(sales):
    """Sum of revenue across all order lines."""
    return float(sales["revenue"].sum())


def total_gross_profit(sales):
    """Gross profit = revenue - cost of goods (no shipping, tax or overheads)."""
    return float(sales["gross_profit"].sum())


def gross_margin_pct(sales):
    """Gross margin % = gross profit / revenue x 100. Returns 0 if no revenue."""
    revenue = total_revenue(sales)
    if revenue == 0:
        return 0.0
    return total_gross_profit(sales) / revenue * 100


def order_count(sales):
    """Number of distinct orders."""
    return int(sales["order_id"].nunique())


def units_sold(sales):
    """Total units sold."""
    return int(sales["quantity"].sum())


def average_order_value(sales):
    """AOV = total revenue / number of distinct orders. Returns 0 if no orders."""
    orders = order_count(sales)
    if orders == 0:
        return 0.0
    return total_revenue(sales) / orders


def kpi_summary(sales):
    """All headline KPIs in one dictionary (used by the app and the README)."""
    return {
        "revenue": total_revenue(sales),
        "gross_profit": total_gross_profit(sales),
        "gross_margin_pct": gross_margin_pct(sales),
        "orders": order_count(sales),
        "units_sold": units_sold(sales),
        "average_order_value": average_order_value(sales),
    }


# ---------------------------------------------------------------------------
# Small summary tables
# ---------------------------------------------------------------------------

def monthly_revenue(sales):
    """Revenue and profit per month, plus month-over-month (MoM) growth %.

    MoM growth % = (this month - last month) / last month x 100
    The first month has no previous month, so its growth is empty (NaN).
    """
    data = sales.copy()
    data["month"] = pd.to_datetime(data["order_date"]).dt.strftime("%Y-%m")
    monthly = data.groupby("month", as_index=False).agg(
        revenue=("revenue", "sum"),
        gross_profit=("gross_profit", "sum"),
    )
    monthly = monthly.sort_values("month").reset_index(drop=True)
    previous = monthly["revenue"].shift(1)
    monthly["mom_growth_pct"] = (monthly["revenue"] - previous) / previous * 100
    return monthly


def build_sales_view(fact_sales, dim_product, dim_region):
    """Join the fact table to its dimensions so each row has readable names.

    This is the same idea as a SQL JOIN on a star schema.
    """
    view = fact_sales.merge(
        dim_product[["product_id", "product_name", "category"]], on="product_id", how="left"
    )
    view = view.merge(dim_region[["region_key", "region_name"]], on="region_key", how="left")
    view = view.rename(columns={"region_name": "region"})
    view["order_date"] = pd.to_datetime(view["order_date"])
    return view
