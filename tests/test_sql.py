"""Every business query must run, and key answers must match pandas."""

import sqlite3

import pandas as pd

from src import metrics, run_sql


def get(results, name):
    """Find one query result by its name."""
    for query_name, _, table in results:
        if query_name == name:
            return table
    raise KeyError(name)


def test_all_queries_run_without_error(built):
    results = run_sql.run_all(db_path=built["db_path"])
    assert len(results) == 10
    for name, description, table in results:
        assert description, f"{name} has no description"
        assert isinstance(table, pd.DataFrame)


def test_query_answers_match_pandas(built):
    results = run_sql.run_all(db_path=built["db_path"])
    fact = built["tables"]["fact_sales"]

    # Duplicate check returns no rows
    assert get(results, "q07_duplicate_order_check").empty

    # Monthly revenue: 12 months that add up to the pandas total
    monthly = get(results, "q01_monthly_revenue_mom")
    assert len(monthly) == 12
    assert abs(monthly["revenue"].sum() - metrics.total_revenue(fact)) < 1

    # Running total ends at the full-year revenue
    running = get(results, "q08_running_total_revenue")
    assert abs(running["running_total_revenue"].iloc[-1] - metrics.total_revenue(fact)) < 1

    # Channel shares add up to ~100%
    assert abs(get(results, "q04_channel_mix")["revenue_share_pct"].sum() - 100) < 0.5

    # Overall AOV matches the Python KPI
    aov = get(results, "q05_average_order_value")
    overall = aov[aov["channel"] == "All channels"]["average_order_value"].iloc[0]
    assert abs(overall - metrics.average_order_value(fact)) < 0.01

    # Top-5 query returns at most 5 ranks per region
    top5 = get(results, "q02_top5_products_per_region")
    assert top5["revenue_rank"].max() <= 5
    assert set(top5["region_name"]) == {"West", "North", "South", "East"}

    # Reorder alerts match the inventory table
    inventory = built["tables"]["fact_inventory"]
    alerts = get(results, "q06_reorder_alerts_last_90_days")
    assert len(alerts) == (inventory["stock_status"] == "Reorder").sum()


def test_warehouse_has_five_tables(built):
    connection = sqlite3.connect(built["db_path"])
    names = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type = 'table'", connection)
    connection.close()
    assert set(names["name"]) == {"dim_product", "dim_region", "dim_date", "fact_sales", "fact_inventory"}
