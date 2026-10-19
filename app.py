"""
app.py - Retail Operations Intelligence dashboard (Streamlit)

Reads the CLEAN, processed data in data/processed/ (created by src/pipeline.py).
If those files are missing (for example on a fresh clone), it runs the
generator + pipeline once to create them.

All data is SYNTHETIC. Run:  streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import metrics  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
REPORT_PATH = ROOT / "reports" / "data_quality_report.md"
REQUIRED_FILES = ["fact_sales.csv", "fact_inventory.csv", "dim_product.csv",
                  "dim_region.csv", "returns_excluded.csv"]

st.set_page_config(page_title="Retail Operations Intelligence", page_icon="📊", layout="wide")


def ensure_processed_data():
    """Create the processed files if they are not in the repo yet."""
    missing = [name for name in REQUIRED_FILES if not (PROCESSED / name).exists()]
    if missing or not REPORT_PATH.exists():
        from src import generate_data, pipeline
        generate_data.generate()
        pipeline.run_pipeline(verbose=False)


@st.cache_data
def load_data():
    """Read the star-schema CSVs and join them into easy-to-use tables."""
    ensure_processed_data()
    fact_sales = pd.read_csv(PROCESSED / "fact_sales.csv")
    fact_inventory = pd.read_csv(PROCESSED / "fact_inventory.csv")
    dim_product = pd.read_csv(PROCESSED / "dim_product.csv")
    dim_region = pd.read_csv(PROCESSED / "dim_region.csv")
    returns = pd.read_csv(PROCESSED / "returns_excluded.csv")

    sales = metrics.build_sales_view(fact_sales, dim_product, dim_region)

    inventory = fact_inventory.merge(dim_product, on="product_id", how="left")
    inventory = inventory.merge(dim_region, on="region_key", how="left")
    inventory = inventory.rename(columns={"region_name": "region"})
    return sales, inventory, returns


sales, inventory, returns = load_data()

st.title("📊 Retail Operations Intelligence")
st.caption("Portfolio demonstration • **Synthetic data only** • Revenue, profitability, "
           "inventory and data-quality checks")

# ---------------------------------------------------------------- Filters
with st.sidebar:
    st.header("Filters")
    min_date = sales["order_date"].min().date()
    max_date = sales["order_date"].max().date()
    picked_dates = st.date_input("Order date range", value=(min_date, max_date),
                                 min_value=min_date, max_value=max_date)
    all_regions = sorted(sales["region"].unique())
    region_filter = st.multiselect("Region", all_regions, default=all_regions)
    all_categories = sorted(sales["category"].unique())
    category_filter = st.multiselect("Category", all_categories, default=all_categories)
    all_channels = sorted(sales["channel"].unique())
    channel_filter = st.multiselect("Channel", all_channels, default=all_channels)

# The date picker returns one date while the user is still choosing the second one
if isinstance(picked_dates, tuple) and len(picked_dates) == 2:
    start_date = pd.Timestamp(picked_dates[0])
    end_date = pd.Timestamp(picked_dates[1])
else:
    start_date = pd.Timestamp(min_date)
    end_date = pd.Timestamp(max_date)

keep = (
    (sales["order_date"] >= start_date)
    & (sales["order_date"] <= end_date)
    & sales["region"].isin(region_filter)
    & sales["category"].isin(category_filter)
    & sales["channel"].isin(channel_filter)
)
df = sales[keep].copy()

if df.empty:
    st.warning("No rows match the filters. Change your selection.")
    st.stop()

# ---------------------------------------------------------------- KPI cards
kpi = metrics.kpi_summary(df)
# Two rows of three cards so large rupee values are not cut off
row1 = st.columns(3)
row1[0].metric("Revenue", f"₹{kpi['revenue']:,.0f}")
row1[1].metric("Gross profit", f"₹{kpi['gross_profit']:,.0f}")
row1[2].metric("Gross margin", f"{kpi['gross_margin_pct']:.1f}%")
row2 = st.columns(3)
row2[0].metric("Orders", f"{kpi['orders']:,}")
row2[1].metric("Avg order value", f"₹{kpi['average_order_value']:,.0f}")
row2[2].metric("Units sold", f"{kpi['units_sold']:,}")

overview_tab, products_tab, inventory_tab, quality_tab, data_tab = st.tabs(
    ["Executive Overview", "Product Performance", "Inventory Actions", "Data Quality", "Data Explorer"]
)

# ---------------------------------------------------------------- Overview
with overview_tab:
    monthly = metrics.monthly_revenue(df)
    left, right = st.columns(2)
    left.plotly_chart(px.line(monthly, x="month", y="revenue", markers=True,
                              title="Monthly revenue (₹)"), width="stretch")
    right.plotly_chart(px.bar(monthly, x="month", y="mom_growth_pct",
                              title="Month-over-month revenue growth (%)"), width="stretch")

    by_region = df.groupby("region", as_index=False).agg(revenue=("revenue", "sum"),
                                                         gross_profit=("gross_profit", "sum"))
    by_channel = df.groupby("channel", as_index=False).agg(revenue=("revenue", "sum"))
    left, right = st.columns(2)
    left.plotly_chart(px.bar(by_region, x="region", y=["revenue", "gross_profit"], barmode="group",
                             title="Revenue and gross profit by region (₹)"), width="stretch")
    right.plotly_chart(px.pie(by_channel, names="channel", values="revenue",
                              title="Channel mix (share of revenue)"), width="stretch")

# ---------------------------------------------------------------- Products
with products_tab:
    perf = df.groupby(["product_id", "product_name", "category"], as_index=False).agg(
        revenue=("revenue", "sum"), gross_profit=("gross_profit", "sum"), units=("quantity", "sum"))
    perf["margin_pct"] = (perf["gross_profit"] / perf["revenue"] * 100).round(1)
    left, right = st.columns(2)
    top10 = perf.nlargest(10, "revenue").sort_values("revenue")
    left.plotly_chart(px.bar(top10, x="revenue", y="product_name", orientation="h",
                             title="Top 10 products by revenue (₹)"), width="stretch")
    right.plotly_chart(px.scatter(perf, x="revenue", y="gross_profit", size="units", color="category",
                                  hover_name="product_name", title="Revenue vs gross profit"),
                       width="stretch")
    st.dataframe(perf.sort_values("revenue", ascending=False), width="stretch", hide_index=True)

# ---------------------------------------------------------------- Inventory
with inventory_tab:
    inv = inventory[inventory["region"].isin(region_filter)
                    & inventory["category"].isin(category_filter)].copy()
    actions = []
    for _, row in inv.iterrows():
        actions.append(metrics.recommended_action(row["on_hand_units"], row["reorder_point"],
                                                  row["target_stock"]))
    inv["recommended_action"] = actions

    a, b, c, d = st.columns(4)
    a.metric("Reorder alerts", int((inv["stock_status"] == "Reorder").sum()))
    b.metric("Healthy", int((inv["stock_status"] == "Healthy").sum()))
    c.metric("Overstock alerts", int((inv["stock_status"] == "Overstock").sum()))
    d.metric("Inventory value (at cost)", f"₹{inv['inventory_value'].sum():,.0f}")

    status_choice = st.radio("Show", ["Reorder", "Overstock", "Healthy", "All"], horizontal=True)
    if status_choice != "All":
        inv = inv[inv["stock_status"] == status_choice]
    show_columns = ["region", "product_name", "category", "on_hand_units", "reorder_point",
                    "target_stock", "stock_status", "inventory_value", "recommended_action"]
    st.dataframe(inv[show_columns].sort_values("on_hand_units"), width="stretch", hide_index=True)
    st.caption("Rule: Reorder if on hand ≤ reorder point; Overstock if on hand > target stock. "
               "Inventory snapshot is synthetic and dated 2025-12-31; it is not live stock data.")

# ---------------------------------------------------------------- Data quality
with quality_tab:
    st.info(f"{len(returns)} return rows ({int(-returns['quantity'].sum())} units) were kept out of "
            "revenue and saved to data/processed/returns_excluded.csv.")
    st.markdown(REPORT_PATH.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- Explorer
with data_tab:
    download = df.copy()
    download["order_date"] = download["order_date"].dt.strftime("%Y-%m-%d")
    st.download_button("Download filtered transactions CSV", download.to_csv(index=False).encode("utf-8"),
                       file_name="filtered_sales.csv", mime="text/csv")
    st.dataframe(df.sort_values("order_date", ascending=False), width="stretch", hide_index=True)

with st.expander("Methodology and limitations"):
    st.write("All data is synthetic and generated for portfolio demonstration with a fixed seed. "
             "No real company, client, performance or savings are claimed.")
    st.write("Gross profit = revenue − cost of goods. It excludes shipping, returns, taxes and "
             "operating expenses, so it is not net profit.")
    st.write("Returns (negative quantities) are excluded from revenue and shown separately.")
