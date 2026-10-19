"""Compare Power BI DAX results (from run_dax_checks.ps1) with SQL run on data/warehouse.db.

Usage:  python powerbi/tools/reconcile.py powerbi/tools/dax_results.json
Prints a Markdown reconciliation table; exit code 1 if anything does not match.
Money is compared to 0.01, percentages to 0.0001 (i.e. 0.01 percentage points), counts exactly.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sql_truth() -> dict:
    con = sqlite3.connect(ROOT / "data" / "warehouse.db")
    one = lambda q: con.execute(q).fetchone()  # noqa: E731
    rev, cost, gp, orders, units = one(
        "SELECT SUM(revenue), SUM(cost), SUM(gross_profit), COUNT(DISTINCT order_id), SUM(quantity) FROM fact_sales")
    t = {"Total Revenue": rev, "Total Cost": cost, "Gross Profit": gp, "Gross Margin %": gp / rev,
         "Orders": orders, "Units Sold": units, "Avg Order Value": rev / orders, "Revenue Share %": 1.0}
    inv = one("""SELECT SUM(i.inventory_value), SUM(i.on_hand_units),
                   SUM(i.stock_status='Reorder'), SUM(i.stock_status='Overstock'), SUM(i.stock_status='Healthy'),
                   SUM(CASE WHEN i.stock_status='Reorder' THEN p.target_stock - i.on_hand_units END),
                   SUM(CASE WHEN i.stock_status='Overstock' THEN i.on_hand_units - p.target_stock END),
                   SUM(CASE WHEN i.stock_status<>'Healthy' THEN i.on_hand_units END),
                   SUM(CASE WHEN i.stock_status<>'Healthy' THEN i.inventory_value END)
                 FROM fact_inventory i JOIN dim_product p USING (product_id)""")
    for k, v in zip(["Inventory Value", "On Hand Units", "Reorder Alerts", "Overstock Alerts", "Healthy Items",
                     "Units To Reorder", "Excess Units", "Alert On Hand Units", "Alert Inventory Value"], inv):
        t[k] = v
    # Returns are not loaded into SQLite; read the pipeline's CSV directly.
    with open(ROOT / "data" / "processed" / "returns_excluded.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    t["Returned Lines"] = len(rows)
    t["Returns Units"] = -sum(int(r["quantity"]) for r in rows)
    t["Returns Value"] = sum(-int(r["quantity"]) * float(r["unit_price"]) * (1 - float(r["discount_pct"])) for r in rows)

    months = con.execute("""SELECT d.year_month, SUM(s.revenue) FROM fact_sales s
                            JOIN dim_date d ON d.date_key = s.date_key GROUP BY 1 ORDER BY 1""").fetchall()
    t["by_month"] = {}
    prev, ytd = None, 0.0
    for ym, r in months:
        ytd += r
        t["by_month"][ym] = {"Total Revenue": r, "Revenue PM": prev,
                             "MoM Growth %": None if prev is None else (r - prev) / prev, "Revenue YTD": ytd}
        prev = r
    t["by_category"] = {c: {"Total Revenue": r, "Gross Profit": g, "Gross Margin %": g / r} for c, r, g in con.execute(
        """SELECT p.category, SUM(s.revenue), SUM(s.gross_profit) FROM fact_sales s
           JOIN dim_product p USING (product_id) GROUP BY 1""")}
    t["by_channel"] = {c: {"Orders": o, "Total Revenue": r, "Revenue Share %": r / rev, "Avg Order Value": r / o}
                       for c, o, r in con.execute(
                           "SELECT channel, COUNT(DISTINCT order_id), SUM(revenue) FROM fact_sales GROUP BY 1")}
    t["by_region"] = {n: {"Orders": o, "Total Revenue": r, "Gross Profit": g, "Gross Margin %": g / r,
                          "Revenue Share %": r / rev} for n, o, r, g in con.execute(
        """SELECT r.region_name, COUNT(DISTINCT s.order_id), SUM(s.revenue), SUM(s.gross_profit)
           FROM fact_sales s JOIN dim_region r USING (region_key) GROUP BY 1""")}
    t["by_status"] = {s: {"Rows": n, "On Hand Units": u, "Inventory Value": v} for s, n, u, v in con.execute(
        "SELECT stock_status, COUNT(*), SUM(on_hand_units), SUM(inventory_value) FROM fact_inventory GROUP BY 1")}
    return t


def fmt(name: str, v) -> str:
    if v is None:
        return "BLANK"
    if "%" in name:
        return f"{v * 100:.2f}%"
    if isinstance(v, float) and not float(v).is_integer() or name in {
            "Total Revenue", "Total Cost", "Gross Profit", "Avg Order Value", "Inventory Value", "Returns Value",
            "Alert Inventory Value", "Revenue PM", "Revenue YTD"}:
        return f"₹{v:,.2f}"
    return f"{int(v):,}"


def same(name: str, a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    tol = 1e-4 if "%" in name else 0.005
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    dax = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    truth = sql_truth()
    rows, bad = [], 0

    def check(label: str, name: str, d, s):
        nonlocal bad
        ok = same(name, d, s)
        bad += not ok
        rows.append(f"| {label} | {fmt(name, d)} | {fmt(name, s)} | {'yes' if ok else '**NO**'} |")

    totals = dax["totals"][0]
    for k, v in truth.items():
        if not k.startswith("by_"):
            check(k, k, totals.get(k), v)
    for section, key in [("by_month", "Year Month"), ("by_category", "Category"), ("by_channel", "Channel"),
                         ("by_region", "Region"), ("by_status", "Stock Status")]:
        got = {r[key]: r for r in dax[section]}
        for member, measures in truth[section].items():
            for m, v in measures.items():
                check(f"{m} — {member}", m, got.get(member, {}).get(m), v)
    print("| Measure (filter) | DAX result | SQL result | Match? |")
    print("|---|---:|---:|:---:|")
    print("\n".join(rows))
    print(f"\n{len(rows) - bad} of {len(rows)} checks match.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
